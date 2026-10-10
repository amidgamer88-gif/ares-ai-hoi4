# GitHub release checklist

The initial public repository upload is complete. The Companion and supporting source have an MIT license with a documented scope. Mod terms and in-game validation remain open release tasks.

- [x] Publish the prototype repository and invite community contributions.

- [x] License original Companion, Bridge, community receiver, tests, and support files under MIT; exclude `mod/` explicitly.
- [ ] Confirm the intended separate reuse terms for original files under `mod/` against applicable Paradox terms.
- [ ] Confirm all included code, names, and assets are original or redistributable; do not add game files, DLC, binary tokens, or player saves.
- [ ] Test the mod marker and AI strategies in the current HOI4 release with debug logging enabled.
- [ ] Confirm the marker's persistence and behavior when ARES is disabled or another mod also uses `on_actions`.
- [ ] Run `Проверить_тесты.bat` and review the archive contents.
- [ ] Decide whether the community feature remains local-only or is replaced by a separately secured public service.
- [ ] Publish a data policy and consent flow before collecting reports from other players.
- [ ] Add repository owner, contribution terms, support contact, and release version.
