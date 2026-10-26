# DILARA Browser integration notes

## Current integration

- The custom browser is implemented in `browser/browser_app.py` using PyQt6 and Qt WebEngine (Chromium).
- `browser/browser_adapter.py` launches it as a separate process. This is intentional: the desktop shell is Tkinter, and Qt widgets/event loops are not embedded into it.
- `main.py` exposes a **BROWSER** workspace, passes an optional initial address to the browser, and uses a per-DILARA-user data directory inside that user's unlocked vault.
- Activity logging records browser lifecycle metadata only; it must not record addresses, search terms, cookies, or page content.
- Browser process tracking prevents duplicate launches from this shell instance. Sign-out and shutdown require the user to close the browser first so its profile is not still in use when the vault is sealed.

## Verified boundaries and remaining work

1. Unit-test the adapter without Qt by mocking the process launcher (`tests/test_browser_adapter.py`).
2. Install `browser/requirements.txt` on the target Windows machine and test the actual Qt WebEngine runtime there.
3. Test address normalization, redirects, pop-ups/new-window tabs, download blocking, and denied site permissions.
4. IPC is not implemented: the shell cannot focus an existing browser, send a URL to an existing instance, or request graceful close. The user can use the browser's own window controls and Windows taskbar.
5. The profile is persistent, not incognito. Per-user paths provide application-level separation only; they are not a replacement for Windows ACLs.
6. This prototype has not undergone a browser security audit and is not a hardened replacement for a maintained mainstream browser in high-risk scenarios.

## Dependency policy

Keep core dependencies in the root `requirements.txt`. Install the optional browser dependencies separately with:

```powershell
py -3 -m pip install -r browser/requirements.txt
```
