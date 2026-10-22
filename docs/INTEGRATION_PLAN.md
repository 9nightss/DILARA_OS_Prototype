# Integration plan and current status

1. **Desktop shell — implemented foundation.** Internal overlapping windows, taskbar, navigation, focus/minimize/maximize/resize/drag and geometry-only layout persistence. GUI still needs runtime validation on Windows.
2. **Shared activity interface — initial implementation.** Shell lifecycle and module actions use `services/activity_log.py`; KOD8 is reached through `services/kod8_adapter.py`.
3. **KOD8 dual role — initial integration.** CL1–CL8 and the original UI are preserved; KOD8 launches as a separate process and CL1 is used for activity-log envelopes. See `KOD8_ACTIVITY_LOGGING.md` for explicit limitations.
4. **DSPACE — functional first pass.** Local JSON resource registry, country/region + label + URL fields, add/remove, persisted data and double-click URL opening.
5. **CYBERSTORM — functional first pass.** Separate JSON registry for FTP/remote URLs, add/remove and external handler launch. Real FTP authentication/session management is not implemented.
6. **EYE — registry first pass.** Camera entries can be saved and opened in the system URL handler. This is not yet a decoded multi-feed camera matrix; RTSP support depends on installed Windows handlers.
7. **D-ARCADE — source launch adapters.** Preserved selected legacy Chess, Tetris, Lightcycle, Maze and Tic-tac-toe sources in `legacy_modules/`. Launches as child processes; Pillow/Pygame dependencies and each game's runtime behavior need Windows testing. Child-process termination tracking is not implemented yet.
8. **D-LLM — custom core selected.** `dilara_core.py` is the in-progress custom chatbot and is the current launch target. `dilara_core_v2.py` remains preserved as a separate Ollama-based legacy experiment and is not part of the normal D-LLM route. Review optional dependencies and voice-network behavior before calling the custom core fully offline.
9. **D-TERMINAL — standard PowerShell launcher.** Launches a normal PowerShell process on Windows; no command is auto-executed and there is no automatic elevation. Per-action elevation is not implemented.
10. **CHAOS — bounded TCP check.** One user-confirmed TCP connection check to a specified host and port, with a three-second timeout and cancellation request. Cancellation cannot interrupt the underlying blocking connect immediately; it reports the limit. No port ranges, scanning sweeps, flooding or packet generation.
11. **Remaining work.** Build a real EYE camera grid/stream lifecycle, improve process tracking and shutdown, test dependency manifests, inspect legacy utilities/destructive actions, harden resource validation, and validate the full GUI on Windows.
12. **Motion tessellation + app registration fixes.** Desktop background now animates a restrained triangular tessellation at roughly 8 FPS; app windows and controls are not animated. Apps & Users includes a Browse picker for Python scripts/folders, URL-specific guidance, automatic ID/name suggestions, and registry path/scheme validation. These changes pass syntax and unit tests but still need GUI runtime validation on Windows.
13. **Packaging.** ZIP is a portable source bundle; it is not yet a signed executable or installer. Verify on a clean Windows environment before distribution.


## DILARA Browser integration (current)

- Added a `BROWSER` desktop workspace and sidebar entry. It launches `browser/browser_app.py` as a child process; Qt WebEngine is not embedded into Tkinter.
- Browser profile, cookies, cache, and history are isolated under `data/users/<username>/browser_data/` through `DILARA_BROWSER_DATA`.
- The shell records only browser lifecycle metadata, not URLs or search terms.
- Install optional dependencies from `browser/requirements.txt` to enable the browser. The core shell remains standard-library-only.
- IPC, cross-process focus, URL handoff to an already-running instance, and graceful close messaging remain future work. The browser is not force-terminated when its shell workspace closes.
