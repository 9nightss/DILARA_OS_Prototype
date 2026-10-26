# Integration plan and current status

1. **Desktop shell — implemented foundation.** Internal overlapping windows, taskbar, navigation, focus/minimize/maximize/resize/drag and geometry-only layout persistence. GUI still needs runtime validation on Windows.
2. **Shared activity interface — initial implementation.** Shell lifecycle and module actions use `services/activity_log.py`; KOD8 is reached through `services/kod8_adapter.py`.
3. **KOD8 dual role — initial integration.** CL1–CL8 and the original UI are preserved; KOD8 launches as a separate process and CL1 is used for activity-log envelopes. See `KOD8_ACTIVITY_LOGGING.md` for explicit limitations.
4. **DSPACE — functional first pass.** Local JSON resource registry, country/region + label + URL fields, add/remove, persisted data and double-click URL opening.
5. **CYBERSTORM — functional first pass.** Separate JSON registry for FTP/remote URLs, add/remove and external handler launch. Real FTP authentication/session management is not implemented.
6. **EYE — registry first pass.** Camera entries can be saved and opened in the system URL handler. This is not yet a decoded multi-feed camera matrix; RTSP support depends on installed Windows handlers.
7. **D-ARCADE — source launch adapters.** Preserved selected legacy Chess, Tetris, Lightcycle, Maze and Tic-tac-toe sources in `legacy_modules/`. Launches as child processes; Pillow/Pygame dependencies and each game's runtime behavior need Windows testing. Child-process termination tracking is not implemented yet.
8. **D-LLM — custom core selected.** `dilara_core.py` is the in-progress custom chatbot and is the current launch target. `dilara_core_v2.py` remains preserved as a separate Ollama-based legacy experiment and is not part of the normal D-LLM route. Review optional dependencies and voice-network behavior before calling the custom core fully offline.
9. **D-TERMINAL — embedded PowerShell console.** A dedicated standard-user process is attached to the workspace through input/output pipes; saved desktop restore never resumes it. Full-screen interactive terminal programs may not work, and there is no automatic elevation.
10. **CHAOS — bounded TCP check.** One user-confirmed TCP connection check to a specified host and port, with a three-second timeout and cancellation request. Cancellation cannot interrupt the underlying blocking connect immediately; it reports the limit. No port ranges, scanning sweeps, flooding or packet generation.
11. **Remaining work.** Build a real EYE camera grid/stream lifecycle, improve process tracking and shutdown, test dependency manifests, inspect legacy utilities/destructive actions, harden resource validation, and validate the full GUI on Windows.
12. **Wallpaper + app registration updates.** The animated tessellation has been removed; the desktop defaults to a static solid color and supports user-selected still images or GIFs. Apps & Users includes a Browse picker for Python scripts/folders, URL-specific guidance, automatic ID/name suggestions, and registry path/scheme validation. These changes pass syntax and unit tests but still need GUI runtime validation on Windows.
13. **Packaging.** ZIP is a portable source bundle; it is not yet a signed executable or installer. Verify on a clean Windows environment before distribution.


## DILARA Browser integration (current)

- Added a `BROWSER` desktop workspace and sidebar entry. It launches `browser/browser_app.py` as a child process and uses Windows native-window reparenting to host it inside the Tk workspace.
- Browser profile, cookies, cache, and history are isolated under `data/users/<username>/browser_data/` through `DILARA_BROWSER_DATA`.
- The shell records only browser lifecycle metadata, not URLs or search terms.
- Install optional dependencies from `browser/requirements.txt` to enable the browser. The core shell remains standard-library-only.
- URL handoff to an already-running instance remains future work. Closing the workspace terminates its browser process; native embedding still needs runtime validation on Windows.

## Recent shell UX updates

- Wallpaper defaults to a static solid color; users can select a color, still image, or animated GIF. Choices persist per user.
- NOTEPAD is available as an in-shell UTF-8 text editor.
- Stack workspace combines compatible in-shell modules in tabs. D-LLM, D-ARCADE, and standalone KOD8 remain separate class applications.
- Browser native-window embedding is implemented as a Windows-specific bridge and still requires runtime verification on the target machine.
