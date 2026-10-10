"""Transparent, local-only ARES prototype heuristics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SnapshotError(ValueError):
    pass


@dataclass(frozen=True)
class Recommendation:
    priority: str
    title: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"priority": self.priority, "title": self.title, "detail": self.detail}


def validate_snapshot(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SnapshotError("Снимок должен быть JSON-объектом.")
    country = raw.get("country", "UNK")
    if not isinstance(country, str) or len(country) != 3 or not country.isalpha():
        raise SnapshotError("Поле country должно быть трёхбуквенным тегом страны, например GER.")
    war = raw.get("at_war", False)
    if not isinstance(war, bool):
        raise SnapshotError("Поле at_war должно быть true или false.")
    stock = raw.get("stockpile_days", {})
    factories = raw.get("factories", {})
    if not isinstance(stock, dict) or not isinstance(factories, dict):
        raise SnapshotError("stockpile_days и factories должны быть объектами.")
    for key, value in stock.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise SnapshotError(f"Запас '{key}' должен быть неотрицательным числом дней.")
    for key, value in factories.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise SnapshotError(f"Фабрики '{key}' должны быть неотрицательным числом.")
    for key in ("stability", "air_superiority"):
        if key in raw and (not isinstance(raw[key], (int, float)) or not 0 <= raw[key] <= 1):
            raise SnapshotError(f"{key} должен быть числом от 0 до 1.")
    if "manpower" in raw and (not isinstance(raw["manpower"], (int, float)) or raw["manpower"] < 0):
        raise SnapshotError("manpower должен быть неотрицательным числом.")
    return raw


def analyze_snapshot(snapshot: dict[str, Any]) -> list[Recommendation]:
    s = validate_snapshot(snapshot)
    stock = {str(k).lower(): float(v) for k, v in s.get("stockpile_days", {}).items()}
    recs: list[Recommendation] = []
    if s.get("at_war"):
        recs.append(Recommendation("info", "Военный режим", "Мод повышает базовые производственные веса во время войны. Проверьте снабжение и не переносите все фабрики на один тип."))
    else:
        recs.append(Recommendation("info", "Мирный режим", "Мод использует более умеренные веса для пехотного и вспомогательного снаряжения."))
    for item, label in (("infantry_equipment", "Пехотное снаряжение"), ("artillery_equipment", "Артиллерия"), ("support_equipment", "Вспомогательное снаряжение"), ("trucks", "Грузовики")):
        if item in stock and stock[item] < 7:
            recs.append(Recommendation("high" if stock[item] < 3 else "medium", f"Низкий запас: {label}", f"Оценка запаса — {stock[item]:g} дней. Проверьте производственные линии и расход на фронте."))
    if "manpower" in s and s["manpower"] < 100_000:
        recs.append(Recommendation("high", "Мало людских ресурсов", "Осталось менее 100 000 manpower. Избегайте лишнего расширения армии и проверьте закон о призыве."))
    if s.get("air_superiority", 1) < 0.25 and s.get("at_war"):
        recs.append(Recommendation("medium", "Слабость в воздухе", "Оценка превосходства ниже 25%. Проверьте доступные самолёты, аэродромы и снабжение авиации."))
    if s.get("stability", 1) < 0.35:
        recs.append(Recommendation("medium", "Низкая стабильность", "Стабильность ниже 35%. Проверьте национальные духи и политические решения."))
    if len(recs) == 1:
        recs.append(Recommendation("ok", "Срочных сигналов нет", "По переданным полям эвристики не нашли явной нехватки. Это не оценка всей ситуации на карте."))
    return recs
