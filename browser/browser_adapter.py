"""Process adapter for the Qt browser used by the Tkinter DILARA shell.

The browser intentionally runs out-of-process because Qt widgets cannot be hosted directly
inside Tkinter. On Windows, the shell can reparent the browser top-level native window into
a Tk workspace frame. Browser profile/history data is isolated per DILARA user through
DILARA_BROWSER_DATA.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

BROWSER_ENTRY = Path(__file__).with_name("browser_app.py")


def launch_browser(
    url: str | None = None,
    *,
    extra_args: Sequence[str] = (),
    data_dir: str | Path | None = None,
) -> subprocess.Popen:
    """Launch DILARA Browser and return the child-process handle.

    ``url`` is passed to the browser only; callers should not copy it into activity logs.
    ``data_dir`` selects the browser's profile/history root, allowing per-user isolation.
    """
    if not BROWSER_ENTRY.is_file():
        raise FileNotFoundError(f"DILARA Browser entry point not found: {BROWSER_ENTRY}")
    command = [sys.executable, str(BROWSER_ENTRY)]
    if url:
        command.append(url)
    command.extend(extra_args)
    env = os.environ.copy()
    if data_dir is not None:
        env["DILARA_BROWSER_DATA"] = str(Path(data_dir).expanduser().resolve())
    return subprocess.Popen(command, cwd=str(BROWSER_ENTRY.parents[1]), env=env)


class BrowserAdapter:
    """Lifecycle tracker compatible with the shell's launcher callback."""

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir).expanduser() if data_dir is not None else None
        self.process: subprocess.Popen | None = None

    def launch(self, url: str | None = None) -> subprocess.Popen:
        if self.is_running():
            raise RuntimeError("DILARA Browser is already running; IPC is not implemented yet.")
        self.process = launch_browser(url, data_dir=self.data_dir)
        return self.process

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def request_close(self) -> None:
        """Intentionally does not force-terminate the browser; close it in its own UI."""
        return None
