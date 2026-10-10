# Contributing to ARES

Thanks for helping test the prototype. ARES is in early development, so community contributions are more than welcome. The game-side marker and strategy behavior still need validation in HOI4.

## Good contributions

- Confirm whether the marker appears in a new plaintext save with ARES enabled.
- Test a save from the current HOI4 version and report which fields parse correctly.
- Improve diagnostics or add synthetic, non-personal parser fixtures.
- Suggest explainable strategy changes and describe a reproducible comparison against vanilla.
- Report conflicts with other mods, including the HOI4 version and relevant error-log lines.

## Before opening an issue or pull request

- Run `Проверить_тесты.bat` on Windows, or run the Python `unittest` suites from the project root.
- Include the game version, enabled mod set, steps to reproduce, and observed versus expected behavior.
- Keep example saves synthetic. Never upload a personal campaign save, Steam account information, game files, DLC, or another player's data.
- Remove usernames and local file paths from log excerpts.
- Keep changes focused and update the relevant Russian and English documentation when behavior changes.

## Current boundaries

- The Companion reads plaintext autosaves only; it does not modify them.
- ARES markers persist in a campaign save and do not prove the mod is currently active.
- The local receiver is bound to `127.0.0.1`; do not expose it to the Internet.
- The project has no selected license yet. Licensing and contributor terms must be settled before a public release that invites reuse.
