# DILARA Browser integration

DILARA Browser is included at `browser/` and appears as the **BROWSER** workspace. It is a custom PyQt6 application using Qt WebEngine (Chromium). Since Qt widgets cannot be hosted directly in Tkinter, the browser runs as a child process; on Windows, DILARA reparents its native top-level window into a frame inside the workspace.

## Enable the browser

From the DILARA project root, install the browser dependencies:

```powershell
py -3 -m pip install -r browser/requirements.txt
```

Then start DILARA and open **BROWSER**. The browser starts automatically inside the workspace; use its own address/search bar to navigate. URL handoff to an already-running browser instance is not implemented yet.

## Included behavior

- Custom dark interface, tabs, navigation, address/search bar, home page, and keyboard shortcuts.
- Dedicated persistent Chromium profile, cookies, cache, and minimal local history.
- JavaScript and image-loading controls, clear-history and cookie/cache controls.
- Site feature permissions denied by default and downloads blocked.
- No bookmarks, download manager, or password-saving feature.
- Browser native window is intended to be hosted inside the DILARA workspace on Windows; on other platforms it remains a separate window.

## Integration and privacy boundaries

- The shell starts the browser with `DILARA_BROWSER_DATA` set to a directory under the active DILARA user's vault, separating profile/history data between DILARA application users. This is application-level separation, not a replacement for Windows account/ACL isolation.
- The activity log records lifecycle metadata (`browser_launched`) only. The shell does not log addresses or search terms.
- The adapter tracks the process and prevents duplicate launches. URL handoff/IPC is not implemented. Closing the BROWSER workspace or DILARA terminates its browser process so the vault is not sealed while the browser is still using it.
- The profile is persistent, not private/incognito. Clearing browser history does not clear cookies/cache; use the separate privacy controls for those.
- Native-window reparenting and Qt WebEngine runtime behavior must be tested on the target Windows machine with the optional dependencies installed. This prototype has not undergone a browser security audit and should not be treated as a hardened replacement for a maintained mainstream browser in high-risk scenarios.
