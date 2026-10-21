# DILARA 5.0 archive — preliminary inventory

Archive inspected: `Dilara 5.0.zip` (80 MB; 2,555 archive entries, including vendored Git history and a large set of ASCII animation frames).

## Source inventory observed

- 25 Python source files and 3 `.ps1` files (some `.ps1` files contain Python rather than PowerShell, so extension alone is not a reliable language indicator).
- `D-ARCADE CLASS/`: several Chess variants, Maze variants, Tetris, Lightcycle and Tic-tac-toe. Tkinter and Pygame implementations are mixed; some depend on Pillow and Windows-only `winsound`/`ctypes` behavior.
- `KOD8_ENC/kod8_engine.py` and `KOD8_ENC/kod8_ui.py`: engine and UI candidates.
- `DilaraLLM_demo-main/dilara_core.py` and `dilara_core_v2.py`: two core versions; compare dependencies and API behavior before choosing one.
- `LS CLASS/LS-DeepScan-main/`: system scan utility.
- `LS CLASS/LS-MasterFormat-main/`: removable-drive format/encryption utility. Formatting and encryption can irreversibly destroy data; keep disconnected from default shell actions until strict target confirmation and tests exist.
- `LS CLASS/winsingleshcleanup-main/powercleanup.ps1`: despite its extension, the file begins with Python imports and indented Python functions. Its README describes broad cleanup and system changes without per-action confirmation. Treat it as untrusted legacy code pending repair/review; do not run it as PowerShell or auto-elevate it.
- `PowerShellBadApple-master/`: animation frames and a PowerShell playback script; likely an optional novelty utility, not a core module.
- `8core colorspace/`, `BINARY_to_DNA/`, and `oscyloskop-capcha.py`: additional utilities whose role in the eight-module hub has not been established.

## Gaps in this archive

No filenames matching DSPACE, CYBERSTORM, EYE, CHAOS, or TERMINAL were found. This does not prove their logic is absent from every source dump or another version; it means the current ZIP does not expose them as clearly named source files. Their implementations/data registries need to be located or specified before claiming those workspaces are functional.

## Integration cautions

- Multiple independent entry points and GUI frameworks exist; do not import and run all source files in the shell process.
- Keep Pygame games in child processes initially unless a tested embedding adapter is built.
- Compare both D-LLM versions and inspect dependency/API requirements before selecting a canonical core.
- Treat drive formatting, encryption, cleanup, and privileged command execution as disabled-by-default operations requiring explicit user intent, exact target display, confirmation, and appropriate elevation only at the point of action.
- CHAOS should be limited to authorized, bounded diagnostics with visible scope, cancellation and rate/volume limits.
