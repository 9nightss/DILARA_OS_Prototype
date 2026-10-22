# DILARA Browser integration

DILARA Browser is now included at `browser/` and appears as the **BROWSER** workspace in the desktop sidebar. The shell launches it as a separate process because the desktop uses Tkinter while the browser uses PyQt6/Qt WebEngine; the two GUI toolkits are not embedded into each other.

## Enable the browser

From the DILARA project root, install the optional dependencies:

```powershell
py -3 -m pip install -r browser/requirements.txt
```

Then start DILARA as usual. Open **BROWSER**, optionally enter an address or search phrase, and select **Launch DILARA Browser**. Leave the shell's main `requirements.txt` standard-library-only if you do not need browser functionality.

## Included behavior

- Custom dark interface, tabs, navigation, address/search bar, home page, and keyboard shortcuts.
- Dedicated persistent Chromium profile, cookies, cache, and minimal local history.
- JavaScript and image-loading controls, clear-history and cookie/cache controls.
- Site feature permissions denied by default and downloads blocked.
- No bookmarks, download manager, or password-saving feature.

The browser is Chromium-based through Qt WebEngine; this is a custom browser application, not a new rendering engine.

## Integration and privacy boundaries

- The shell starts the browser with `DILARA_BROWSER_DATA` set to `data/users/<username>/browser_data/`, separating the profile/history directory between DILARA application users. This is application-level separation, not a replacement for Windows account/ACL isolation.
- The activity log records lifecycle metadata (`browser_launched`) only. The shell does not log addresses or search terms.
- The shell adapter tracks the launched process and prevents duplicate launches from the same shell session. If the browser is already running, bring it forward from the Windows taskbar.
- Inter-process communication is not implemented yet: the shell cannot focus an existing browser window, send a new address to it, or request a graceful close. Closing the BROWSER workspace does not close the browser process, and the shell does not force-terminate it at shutdown.
- The profile is persistent, not private/incognito. Clearing browser history does not clear cookies/cache; use the separate privacy controls for those.
- Qt WebEngine runtime behavior must still be tested on the target Windows machine with the optional dependencies installed. This prototype has not undergone a browser security audit and should not be treated as a hardened replacement for a maintained mainstream browser in high-risk scenarios.
