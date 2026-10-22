# Implementation notes

## Initial design choices

- PyQt6 + Qt WebEngine (Chromium renderer)
- Browser UI and behavior are custom; rendering engine is reused
- Dedicated persistent profile, separate from the user's default browser profile
- History is minimal, local, capped at 500 entries, and user-clearable
- No bookmarks, downloads UI/manager, or password-saving feature
- Downloads are blocked and browser feature permissions are denied by default
- The existing Tkinter DILARA shell must launch the browser as a separate process until the shell migration is explicitly undertaken

## Next integration steps

1. Install dependencies and launch on the target Windows machine.
2. Test address normalization, redirects, pop-up/new-window tab behavior, downloads, and permission denial.
3. Patch the current `main.py` to call `launch_browser()` from the Browser module button.
4. Track the returned `Popen` handle in the shell and handle process exit without force-killing unrelated browser instances.
5. Decide whether browser windows remain external OS windows or whether the wider shell is migrated to Qt; do not attempt cross-toolkit widget embedding.
