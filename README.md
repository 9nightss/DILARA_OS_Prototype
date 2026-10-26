# DILARA Desktop Shell Prototype

A Windows-oriented Python/Tkinter desktop shell foundation for DILARA 5.0. Requires Python 3.10+ and `cryptography` for the per-user encrypted vault. Some preserved legacy games need Pillow and/or Pygame.

## Run

- Windows: double-click `run_dilara.bat`, or run `python main.py` from this folder.
- Install core dependency: `py -3 -m pip install -r requirements.txt`.
- Tests: `python -m unittest discover -s tests -v`.

## Implemented in this build

- **Login page and multi-user environment:** first-run administrator setup, local sign-in, PBKDF2-HMAC-SHA256 account verifiers, sign-out, and administrator-created user accounts.
- **Per-user encrypted vault:** each account gets one opaque `.dvault` file. Login unlocks a tree-based virtual root; logout/shutdown archives and encrypts it with AES-GCM, using atomic replacement so a failed commit does not overwrite the existing container. Password preprocessing follows the supplied binary-to-DNA mapping before salted PBKDF2 key derivation. See `docs/DILARA_VAULT.md`.
- **FILES workspace:** browse the user root, create folders and UTF-8 text files, and edit/save text documents.
- **D-LLM workspace:** launches the original in-progress custom chatbot at `legacy_modules/DilaraLLM_demo-main/dilara_core.py`, plus a built-in no-network utility fallback. DILARA does not require Ollama or an external model runtime for its custom D-LLM route. The separate Ollama-based `dilara_core_v2.py` remains preserved for reference but is not offered as the D-LLM launch path.
- **Extensible app registry:** register Python, URL, and folder apps through **Apps & Users**, with a file/folder Browse picker for local apps, or drop a manifest into `apps/<folder>/app.json`. Registry validation rejects missing Python entry points and invalid URL schemes. Discovery never runs app code; Python launches require confirmation. Added apps appear in the app list at the bottom of D-LLM.

- Dark desktop shell with a static blank-color default wallpaper, optional user-selected picture or animated GIF, persistent navigation and overlapping movable/resizable windows. Wallpaper choice persists per DILARA user; no background animation runs unless the user selects a GIF.
- Window focus, minimize, maximize/restore, taskbar and per-user geometry/wallpaper persistence. The Stack workspace combines compatible in-shell tools as tabs; D-LLM and D-ARCADE remain separate class applications.
- **DSPACE:** country/region-based URL registry with local JSON persistence, add/remove, and open-on-double-click.
- **CYBERSTORM:** separate country/region-based FTP/remote-resource registry with local JSON persistence and external handler launch.
- **EYE:** camera/stream registry with location labels and external stream launch. Actual in-window video decoding and the camera-feed matrix remain future work.
- **KOD8:** original source files preserved in `KOD8_ENC/`, including CL1–CL8 and current standalone UI. The UI launches as a side application.
- **DILARA Browser:** integrated as a workspace launcher. The custom PyQt6/Qt WebEngine browser runs in its own process, with a profile/history data root isolated per DILARA application user. The shell logs browser launch lifecycle metadata only, never addresses or search terms. On Windows, the browser process is reparented into its DILARA workspace; this native-window embedding needs runtime validation on the target machine. See `docs/DILARA_BROWSER.md`.
- Separate activity-log API (`services/activity_log.py`) and KOD8 bridge (`services/kod8_adapter.py`). Shell events use the existing CL1 pipeline and are stored in `data/activity.kod8log`.
- **D-ARCADE:** selected original Chess, Tetris, Lightcycle, Maze and Tic-tac-toe sources preserved under `legacy_modules/`; launch buttons start separate processes.
- **D-LLM:** the original custom `dilara_core.py` work-in-progress is the launchable in-house chatbot; the separate Ollama-based v2 experiment is preserved but not launched by the D-LLM workspace.
- **D-TERMINAL:** embedded PowerShell console with a dedicated standard-user process, output/input controls, and explicit session start/stop. Restoring a saved desktop never resumes a terminal session; no elevation is requested. Full-screen interactive console programs may not work in the embedded pipe-based console.
- **CHAOS:** one confirmed TCP connection check for a specified host/port, with a three-second timeout and cancellation request. It is not a scanner or traffic generator.

## Important KOD8 limitation

The user explicitly selected use of the existing KOD8 pipeline as-is for activity logs. The source is preserved, but the current engine uses a hardcoded key and reversible transformations that are not equivalent to the named cryptographic algorithms. It does not provide authenticated encryption or tamper detection. Do not use it as a security boundary for secrets or high-assurance audit logs. Activity logging does not silently fall back to plaintext.

## Important integration limits

- This is a portable source prototype, not a finished OS, signed executable, or installer.
- The vault uses a plaintext staging directory during an active session for compatibility. Abrupt crashes may leave that workspace behind; crash recovery and stale-session detection are not implemented yet. See `docs/DILARA_VAULT.md`.
- The new vault and FILES GUI has not yet been runtime-tested on the target Windows machine.
- DILARA Browser requires the optional dependencies in `browser/requirements.txt`. Pillow is included in core requirements for image resizing and animated GIF wallpapers. The browser runs as a child process and is intended to be reparented into its workspace on Windows; URL handoff to an already-running instance is not implemented and native-window embedding needs target-machine testing.
- Legacy game runtime dependencies and each game's behavior need testing; D-ARCADE processes are not yet tracked for coordinated shutdown.
- The custom D-LLM core remains work in progress. Its optional SpeechRecognition fallback uses Google online speech recognition; Vosk can be used locally when its model is installed.
- EYE currently stores and opens camera URLs but does not render video inside DILARA.
- The CHAOS cancel button can request cancellation, but a blocking TCP connection attempt may continue until its timeout.
- Destructive legacy utilities have not been integrated into the shell.

See `docs/INTEGRATION_PLAN.md`, `docs/ARCHIVE_AUDIT.md`, and `docs/KOD8_ACTIVITY_LOGGING.md` for current gaps and decisions.

See `docs/MULTIUSER_AND_LLM.md` and `apps/README.md` for account boundaries, the custom D-LLM core and utility fallback, and adding future apps. Local app accounts are not Windows accounts; use Windows ACLs for filesystem isolation.
