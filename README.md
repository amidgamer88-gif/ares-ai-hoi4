# ARES AI for Hearts of Iron IV

ARES is an experimental, community-oriented prototype for testing adaptive HOI4 AI strategies. It combines a small game mod with a local Windows companion that watches text autosaves.

**Prototype version:** 0.1 · **Target game version:** Hearts of Iron IV 1.19.3

> **ARES is in early development, so community contributions are more than welcome.** Ideas, in-game compatibility reports, and code improvements can be shared through Issues and Pull Requests.

The long-term idea is to explore whether AI-assisted analysis and opt-in player observations can help make vanilla bots more engaging. Version 0.1 does not connect to ChatGPT, train itself, collect shared player data, or send orders to the game.

**This is not a trained neural network.** The current mod changes a few production priorities; the companion reads a small set of country values and detects an ARES marker written into the save. It does not issue orders to the game or learn from player data yet.

[Русская инструкция](README_RU.md) · [How the Companion works](desktop_app/README_RU.md) · [Sources and compatibility notes](SOURCES.md)

## Current prototype

- Scripted strategies adjust selected equipment priorities between peace and war.
- The mod writes `ares_ai_companion_v1` to human-controlled countries. The Companion reads that persistent country flag from plaintext saves and marks the report as ARES.
- The Companion watches new autosaves, shows basic diagnostics, and stores reports locally by default.
- An optional local-only report receiver is included for integration tests. It is not a public service and does not train a model.

The marker means that ARES was loaded in the campaign at some point. It remains in a save if the mod is later disabled, so it does not prove the mod is active in the current game session. Existing campaigns receive the marker on a weekly hook after the mod is enabled.

## Try it on Windows

1. Install Python 3.10 or newer. The scripts use only the Python standard library.
2. Double-click `Установить_мод.bat`, then enable **ARES AI — Adaptive Response Prototype** in the Paradox Launcher.
3. Double-click `Запустить_Приложение.bat`. If your saves are binary, use the Companion settings to switch future saves to text; it creates a backup of `settings.txt` and never converts existing saves.
4. Start or load a campaign with ARES enabled. Allow at least one in-game week, then wait for a new text autosave. Check the marker status in the Companion.

Run `Проверить_тесты.bat` to execute the parser, marker, local receiver, and Bridge tests.

## Contributing

Useful first contributions include testing the mod in the current HOI4 release, validating the marker in a fresh text save, improving save parsing with synthetic fixtures, and proposing explainable AI strategies. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request.

Do not commit game files, DLC, personal saves, logs with personal data, or telemetry from other players. Use small synthetic save fixtures instead.

## Roadmap

- Verify `on_startup` and `on_weekly` marker behavior in the current game build and with common mod combinations.
- Improve campaign-state parsing and distinguish detected, missing, and unsupported markers.
- Collect opt-in, versioned observations with decision and outcome labels before designing any shared training pipeline.
- Design a secure public service only after the data format, consent, retention, and deletion process are agreed.

## License

The original Companion, Bridge, local community receiver, tests, and project support files are licensed under MIT. Read [the scope note](LICENSE_SCOPE.md) before reusing files; the full license text is in [LICENSES/MIT.txt](LICENSES/MIT.txt). The `mod/` directory is excluded from the MIT grant and has no separate OSI-approved license in this repository. Its distribution remains subject to the applicable Paradox terms for HOI4 user-generated content. The code license does not cover player reports, saves, or future training data.
