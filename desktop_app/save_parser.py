"""Read-only, selective reader for plaintext HOI4 saves (HOI4txt)."""
from __future__ import annotations

import re
from pathlib import Path

TEXT_HEADER = b"HOI4txt"
BINARY_HEADER = b"HOI4bin"
TOKEN = re.compile(r'#.*?$|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=]+', re.MULTILINE)
ROOT_KEYS = {"date", "player", "version", "save_version", "game_version"}
COUNTRY_KEYS = {"stability", "war_support", "manpower", "political_power", "at_war", "surrender_progress"}
ARES_COUNTRY_FLAG = "ares_ai_companion_v1"


class SaveReadError(ValueError):
    pass


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return bytes(value[1:-1], "utf-8").decode("unicode_escape")
    return value


def _scalar(value: str | None):
    if value is None:
        return None
    value = _unquote(value)
    try:
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", value):
            return float(value)
    except ValueError:
        pass
    if value == "yes":
        return True
    if value == "no":
        return False
    return value


def _root_scalars(text: str, wanted: set[str]) -> dict:
    """Extract only unindented root-level scalar fields; avoids parsing the whole save."""
    result = {}
    for key in wanted:
        match = re.search(rf'(?m)^{re.escape(key)}\s*=\s*("(?:\\.|[^"\\])*"|[^\s{{}}#]+)', text)
        if match:
            result[key] = _scalar(match.group(1))
    return result


def _matching_brace(text: str, opening: int) -> int:
    depth = 0
    quoted = escaped = comment = False
    for index in range(opening, len(text)):
        char = text[index]
        if comment:
            if char in "\r\n":
                comment = False
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == "#":
            comment = True
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise SaveReadError("В сохранении не закрыт блок данных страны.")


def _top_scalars(block: str, wanted: set[str]) -> dict:
    """Read scalar fields at the direct level of one country object."""
    result = {}
    depth = 0
    previous = None
    pending = None
    for match in TOKEN.finditer(block):
        token = match.group(0)
        if token.startswith("#"):
            continue
        if token == "{":
            depth += 1
            pending = None
            previous = token
        elif token == "}":
            depth = max(0, depth - 1)
            pending = None
            previous = token
        elif token == "=":
            pending = previous if depth == 0 and previous in wanted else None
            previous = token
        else:
            if depth == 0 and pending:
                result[pending] = _scalar(token)
            pending = None
            previous = token
    return result


def _top_child_block(block: str, wanted: str) -> str | None:
    """Return one direct child block, ignoring same-named blocks at deeper scopes."""
    depth = 0
    previous = None
    expect_block = False
    for match in TOKEN.finditer(block):
        token = match.group(0)
        if token.startswith("#"):
            continue
        if token == "{":
            if depth == 0 and expect_block:
                ending = _matching_brace(block, match.start())
                return block[match.end():ending]
            depth += 1
            expect_block = False
            previous = token
        elif token == "}":
            depth = max(0, depth - 1)
            expect_block = False
            previous = token
        elif token == "=":
            expect_block = depth == 0 and previous == wanted
            previous = token
        else:
            expect_block = False
            previous = _unquote(token)
    return None


def _has_top_level_key(block: str, wanted: str) -> bool:
    """Check whether a key occurs directly in a block (flags may have date values)."""
    depth = 0
    previous = None
    for match in TOKEN.finditer(block):
        token = match.group(0)
        if token.startswith("#"):
            continue
        if token == "{":
            depth += 1
        elif token == "}":
            depth = max(0, depth - 1)
        elif token == "=":
            if depth == 0 and previous == wanted:
                return True
            previous = token
        else:
            previous = _unquote(token)
    return False


def _country_block(text: str, tag: str) -> str:
    countries = re.search(r"(?m)^countries\s*=\s*\{", text)
    if not countries:
        raise SaveReadError("В текстовом сохранении не найден блок countries.")
    # Country entries are direct children and begin on a separate line in HOI4 text saves.
    entry = re.search(rf"(?m)^[\t ]+{re.escape(tag)}\s*=\s*\{{", text[countries.end():])
    if not entry:
        raise SaveReadError(f"Не найден блок страны {tag} в сохранении.")
    opening = countries.end() + entry.end() - 1
    ending = _matching_brace(text, opening)
    return text[opening + 1:ending]


def parse_save(path: str | Path) -> dict:
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise SaveReadError(f"Не удалось прочитать сохранение: {exc}") from exc
    if data.startswith(BINARY_HEADER):
        raise SaveReadError(
            "Это бинарное сохранение. ARES Companion пока читает текстовые сейвы. "
            "В настройках приложения нажмите «Включить текстовые сохранения», "
            "перезапустите HOI4 и дождитесь следующего автосохранения."
        )
    if data.startswith(TEXT_HEADER):
        data = data[len(TEXT_HEADER):]
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SaveReadError("Файл не похож на текстовое сохранение HOI4.") from exc
    if "countries" not in text[:2_000_000]:
        raise SaveReadError("Не найден заголовок countries; сохранение может быть неполным.")

    root = _root_scalars(text, ROOT_KEYS)
    tag = root.get("player")
    if not isinstance(tag, str) or not re.fullmatch(r"[A-Z0-9]{3}", tag):
        raise SaveReadError("Не найден трёхсимвольный тег страны игрока (player) в сейве.")
    country_block = _country_block(text, tag)
    country = _top_scalars(country_block, COUNTRY_KEYS)
    flags_block = _top_child_block(country_block, "flags")
    state = {
        "country": tag,
        "date": root.get("date"),
        "game_version": root.get("game_version") or root.get("version"),
        "save_version": root.get("save_version"),
        "stability": country.get("stability"),
        "war_support": country.get("war_support"),
        "manpower": country.get("manpower"),
        "political_power": country.get("political_power"),
        "at_war": country.get("at_war"),
        "surrender_progress": country.get("surrender_progress"),
        "ares_marker_present": bool(flags_block and _has_top_level_key(flags_block, ARES_COUNTRY_FLAG)),
        "parsed_fields": sorted(k for k, v in country.items() if v is not None),
        "save_format": "text",
    }
    if not state["date"]:
        raise SaveReadError("В сохранении не найдено игровое поле date.")
    return state
