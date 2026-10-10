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

## Licensing contributions

- Contributions to MIT-covered files are submitted under the MIT License. By opening a pull request for those files, you confirm you have the right to contribute the code and agree that it may be distributed under MIT.
- The `mod/` directory is excluded from MIT. Contributions there must be your original work, must be suitable for a free, non-commercial HOI4 mod under Paradox's applicable terms, and must not contain game files, DLC, or other material you do not have rights to share. By submitting a mod contribution, you allow ARES maintainers to include and publish it as part of the ARES HOI4 mod under those applicable terms. This does not grant rights to Paradox or third-party material, or an MIT license for the mod.

## Current boundaries

- The Companion reads plaintext autosaves only; it does not modify them.
- ARES markers persist in a campaign save and do not prove the mod is currently active.
- The local receiver is bound to `127.0.0.1`; do not expose it to the Internet.
- The Companion, Bridge, community receiver, tests, and original project support files use MIT within the scope in [LICENSE_SCOPE.md](LICENSE_SCOPE.md). The `mod/` directory is excluded.
