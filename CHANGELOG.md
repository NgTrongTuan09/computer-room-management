# CHANGELOG

All notable changes to this project are documented in this file.

## [Unreleased] - 2026-05-18

### Added
- `requirements.txt` — project dependencies (PyQt5, OpenCV, numpy, MSS, Pillow).
- `.gitignore` — ignore Python artifacts and OS/editor files.
- `README.md` — comprehensive project README with setup and run instructions.
- `utils/logger.py` — centralized logging system used across the project.

### Changed / Improved
- `core/computer_manager.py` — fixed remove-by-IP bug (use list comprehension), added logging, validation and helper methods (remove_by_id, status updates, counts)
- `network/server.py` — rewrote to add robust logging, thread-safe client registration/removal, socket timeouts, improved error handling, file transfer progress, and graceful shutdown.
- `network/client.py` — improved with logging, reconnection logic, screen-capture error handling, safe file receive/save, and virtual-drive management improvements.
- `main.py` — UI improvements: integrated logging, file transfer progress callbacks/signals, better error handling, timeout checker, improved table and card rendering, and user-friendly messages.

### Notes
- The repo was initialized with a few scaffolding files; after pushing local code you may need to adjust config (e.g., server host/port) and install dependencies via `pip install -r requirements.txt`.
- Personal Access Token is required for HTTPS push if using username/password replacement; prefer using `gh` CLI or SSH keys for convenience.

### Next recommended steps
1. Run the app locally and verify functionality: `python main.py` for server GUI; `python network/client.py` (or `client_main.py` if available) on client machines.
2. Test file transfer and screen streaming on LAN with at least one client and one server.
3. Add unit tests for ComputerManager and network message parsing.
4. Harden security: authentication, encryption for streams, and permission checks for file operations.

---

Generated on 2026-05-18 by GitHub Copilot enhancements
