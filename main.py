from __future__ import annotations
import json
import math
import queue
import threading
import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk, filedialog, colorchooser, simpledialog
from pathlib import Path

from services.activity_log import ActivityLogger, ActivityLogError
from services.kod8_adapter import Kod8Adapter
from services.auth import UserStore, AuthError
from services.vault_manager import VaultManager, VaultError
from services.app_registry import AppRegistry
from services.offline_assistant import respond as offline_respond
from browser.browser_adapter import BrowserAdapter

APP_DIR = Path(__file__).resolve().parent
CONFIG_DIR = APP_DIR / "config"
STATE_FILE = CONFIG_DIR / "desktop_state.json"
USER_STORE_FILE = CONFIG_DIR / "users.json"

BG = "#090d13"
PANEL = "#111923"
PANEL_2 = "#172330"
BORDER = "#2b3b4c"
TEXT = "#e4edf5"
MUTED = "#8fa2b5"
ACCENT = "#4ed6c5"
ACCENT_2 = "#d17dff"
WARN = "#f0b56a"


def _format_file_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024

MODULES = [
    ("DSPACE LIST", "Network atlas", "Country-based resource and site directory."),
    ("FTP LIST", "FTP / remote resources", "Country-based FTP and remote-resource directory."),
    ("THE EYE", "Camera matrix", "Camera registry and multi-feed workspace."),
    ("KOD8", "Cryptographic workspace", "Cipher routing and .kod8 tooling."),
    ("D-ARCADE", "Game library", "Chess, Lightcycle, Tetris, Maze and Tic-tac-toe."),
    ("D-LLM", "Language model", "Local/custom assistant and model services."),
    ("D-TERMINAL", "PowerShell console", "Standard-user console; privileged actions should be explicit."),
    ("CHAOS", "Network diagnostics", "Bounded, authorized diagnostics with scope and cancellation."),
    ("BROWSER", "DILARA Browser", "Custom Chromium-based browser with a dedicated local profile."),
    ("FILES", "Virtual file system", "Per-user directory tree stored in an encrypted single-file vault."),
    ("NOTEPAD", "Text editor", "A lightweight editor for notes and text files."),
    ("STACK", "Stacked workspace", "Combine compatible modules in a tabbed class workspace."),
]

class DesktopWindow:
    def __init__(self, app: "DilaraApp", module: tuple[str, str, str], x: int, y: int, w: int = 560, h: int = 360, stack_keys=None, restoring=False):
        self.app, self.module = app, module
        self.key, self.subtitle, self.description = module
        self.x, self.y, self.w, self.h = x, y, w, h
        self.stack_keys = list(stack_keys or [])
        self.restoring = restoring
        self.maximized = False
        self.restore_geometry = (x, y, w, h)
        self.minimized = False
        self.frame = tk.Frame(app.desktop, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        self.titlebar = tk.Frame(self.frame, bg=PANEL_2, height=36)
        self.titlebar.pack(fill="x")
        self.titlebar.pack_propagate(False)
        tk.Label(self.titlebar, text="  ◈", bg=PANEL_2, fg=ACCENT, font=("Segoe UI", 11, "bold")).pack(side="left")
        self.title_label = tk.Label(self.titlebar, text=f" {self.key}  /  {self.subtitle}", bg=PANEL_2, fg=TEXT, font=("Segoe UI Semibold", 9))
        self.title_label.pack(side="left", fill="y")
        controls = tk.Frame(self.titlebar, bg=PANEL_2)
        controls.pack(side="right", padx=5)
        self._control(controls, "—", self.minimize, MUTED).pack(side="left", padx=2)
        self._control(controls, "□", self.toggle_maximize, ACCENT).pack(side="left", padx=2)
        self._control(controls, "×", self.close, "#ff7585").pack(side="left", padx=2)
        self.body = tk.Frame(self.frame, bg=PANEL, padx=20, pady=18)
        self.body.pack(fill="both", expand=True)
        self._build_content()
        self.grip = tk.Label(self.frame, text="◢", bg=PANEL, fg=MUTED, cursor="size_nw_se")
        self.grip.place(relx=1, rely=1, anchor="se")
        self.grip.bind("<ButtonPress-1>", self._resize_start)
        self.grip.bind("<B1-Motion>", self._resize_motion)
        for widget in (self.titlebar, self.title_label):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_motion)
            widget.bind("<Double-Button-1>", lambda _e: self.toggle_maximize())
        self.frame.bind("<Button-1>", lambda _e: self.focus(), add="+")
        self.frame.bind("<Configure>", lambda _e: self.app.refresh_taskbar(), add="+")
        self.frame.place(x=x, y=y, width=w, height=h)
        self.focus()

    def _control(self, parent, label, command, color):
        return tk.Button(parent, text=label, command=command, bg=PANEL_2, fg=color, activebackground=BORDER,
                         activeforeground=TEXT, relief="flat", bd=0, width=3, font=("Segoe UI", 10), cursor="hand2")

    def _build_content(self):
        if self.key == "STACK":
            self.app.build_stacked_workspace(self)
            return
        if self.key in {"DSPACE", "CYBERSTORM", "EYE", "D-ARCADE", "D-LLM", "D-TERMINAL", "CHAOS", "BROWSER", "FILES", "NOTEPAD"}:
            self.app.build_workspace(self)
            return
        tk.Label(self.body, text=self.key, bg=PANEL, fg=ACCENT, font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(self.body, text=self.subtitle.upper(), bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(1, 13))
        tk.Label(self.body, text=self.description, bg=PANEL, fg=TEXT, font=("Segoe UI", 11), wraplength=480, justify="left").pack(anchor="w")
        tk.Frame(self.body, bg=BORDER, height=1).pack(fill="x", pady=17)
        tk.Label(self.body, text="INTEGRATION STATUS", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        status = "KOD8 CL1–CL8 source is preserved. DILARA activity logging calls it through a separate adapter; the original UI remains a side app."
        tk.Label(self.body, text=status, bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=480, justify="left").pack(anchor="w")
        tk.Button(self.body, text="Launch KOD8 side application", command=self.app.launch_kod8_side_app,
                  bg=ACCENT, fg="#071014", activebackground="#7ce7dc", relief="flat",
                  padx=14, pady=8, font=("Segoe UI Semibold", 9), cursor="hand2").pack(anchor="w", pady=(16, 0))
        tk.Label(self.body, text="Security note: existing transforms are experimental and do not provide authenticated encryption or tamper detection.",
                 bg=PANEL, fg=WARN, font=("Segoe UI", 9), wraplength=480, justify="left").pack(anchor="w", pady=(10, 0))

    def _drag_start(self, event):
        self.focus()
        if self.maximized: return
        self._drag_offset = (event.x_root - self.x, event.y_root - self.y)

    def _drag_motion(self, event):
        if self.maximized or not hasattr(self, "_drag_offset"): return
        self.x = max(0, event.x_root - self._drag_offset[0])
        self.y = max(0, event.y_root - self._drag_offset[1])
        self.frame.place_configure(x=self.x, y=self.y)

    def _resize_start(self, event):
        self.focus()
        self._resize_origin = (event.x_root, event.y_root, self.w, self.h)

    def _resize_motion(self, event):
        if self.maximized or not hasattr(self, "_resize_origin"): return
        sx, sy, sw, sh = self._resize_origin
        self.w = max(340, sw + event.x_root - sx)
        self.h = max(220, sh + event.y_root - sy)
        self.frame.place_configure(width=self.w, height=self.h)

    def focus(self):
        if self.minimized: return
        self.frame.lift()
        self.app.active = self
        self.app.refresh_taskbar()

    def minimize(self):
        self.minimized = True
        self.frame.place_forget()
        if self.app.active is self: self.app.active = None
        self.app.refresh_taskbar()

    def restore(self):
        if self.minimized:
            self.minimized = False
            self.frame.place(x=self.x, y=self.y, width=self.w, height=self.h)
        self.focus()

    def toggle_maximize(self):
        if self.minimized: self.restore()
        if not self.maximized:
            self.restore_geometry = (self.x, self.y, self.w, self.h)
            self.maximized = True
            self.x, self.y = 12, 12
            self.w = max(360, self.app.desktop.winfo_width() - 24)
            self.h = max(240, self.app.desktop.winfo_height() - 24)
        else:
            self.maximized = False
            self.x, self.y, self.w, self.h = self.restore_geometry
        self.frame.place(x=self.x, y=self.y, width=self.w, height=self.h)
        self.focus()

    def close(self):
        self.app._dispose_window(self)
        self.app._record_activity("module_closed", self.key)
        self.frame.destroy()
        self.app.windows.pop(self.key, None)
        if self.app.active is self: self.app.active = None
        self.app.refresh_taskbar()

class DilaraApp:
    def __init__(self, root: tk.Tk, user: dict, vault: VaultManager):
        self.root = root
        self.user = user
        self.vault = vault
        if not self.vault.is_open or self.vault.root is None:
            raise VaultError("Cannot start the desktop without an unlocked user vault.")
        # User-owned state lives inside the unlocked root so it is sealed with the vault.
        self.user_dir = self.vault.root / "Applications" / "DILARA"
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.user_dir / "desktop_state.json"
        self.app_registry = AppRegistry(self.vault.root / "Applications" / "Registry")
        # Browser data is separated by DILARA application user; URLs are never activity-logged.
        self.browser_adapter = BrowserAdapter(self.vault.root / "Applications" / "Browser")
        self.root.title("DILARA // Desktop Environment")
        self.root.geometry("1440x900")
        self.root.minsize(980, 620)
        self.root.configure(bg=BG)
        self.windows: dict[str, DesktopWindow] = {}
        self.active: DesktopWindow | None = None
        self.wallpaper_color = BG
        self.wallpaper_path = None
        self._wallpaper_pil = None
        self._wallpaper_frames = []
        self._wallpaper_frame_index = 0
        self._wallpaper_after_id = None
        self.terminal_sessions = {}
        self._terminal_owner = {}
        self.browser_owner = None
        self._embedded_browser_hwnd = None
        self._embedded_browser_host = None
        self.activity_logger = ActivityLogger(APP_DIR / "data" / "activity.kod8log", Kod8Adapter())
        self._record_activity("session_started", "SYSTEM")
        self._load_state()
        self._build_shell()
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        self.root.after(250, self._restore_layout)

    def _build_shell(self):
        header = tk.Frame(self.root, bg="#0c131c", height=54)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="DILARA", bg="#0c131c", fg=TEXT, font=("Segoe UI", 17, "bold")).pack(side="left", padx=(20, 8))
        tk.Label(header, text="DESKTOP ENVIRONMENT  /  5.0", bg="#0c131c", fg=ACCENT, font=("Consolas", 9)).pack(side="left", pady=(5, 0))
        tk.Label(header, text=f"USER  {self.user['username'].upper()}  /  {self.user['role'].upper()}", bg="#0c131c", fg=MUTED, font=("Consolas", 8)).pack(side="left", padx=20, pady=(5, 0))
        self.clock = tk.Label(header, text="LOCAL SESSION", bg="#0c131c", fg=MUTED, font=("Consolas", 9))
        self.clock.pack(side="right", padx=20)
        self.root.after(1000, self._tick_clock)
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(main, bg="#0d141d", width=205)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="WORKSPACES", bg="#0d141d", fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(20, 10))
        for key, subtitle, desc in MODULES:
            if key == "STACK":
                continue
            btn = tk.Button(self.sidebar, text=f"◈  {key}", command=lambda k=key: self.open_module(k),
                            bg="#0d141d", fg=TEXT, activebackground=PANEL_2, activeforeground=ACCENT,
                            relief="flat", bd=0, anchor="w", padx=16, pady=8, font=("Segoe UI", 9), cursor="hand2")
            btn.pack(fill="x", padx=6, pady=1)
        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x", padx=14, pady=15)
        tk.Label(self.sidebar, text="SESSION", bg="#0d141d", fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(0, 8))
        tk.Button(self.sidebar, text="▧  Wallpaper", command=self.open_wallpaper_menu, bg="#0d141d", fg=ACCENT_2,
                  activebackground=PANEL_2, relief="flat", anchor="w", padx=16, pady=8, font=("Segoe UI", 9)).pack(fill="x", padx=6)
        tk.Button(self.sidebar, text="▤  Stack workspace", command=self.open_stacked_workspace, bg="#0d141d", fg=ACCENT,
                  activebackground=PANEL_2, relief="flat", anchor="w", padx=16, pady=8, font=("Segoe UI", 9)).pack(fill="x", padx=6)
        tk.Button(self.sidebar, text="▣  Save layout", command=self.save_state, bg="#0d141d", fg=ACCENT,
                  activebackground=PANEL_2, relief="flat", anchor="w", padx=16, pady=8, font=("Segoe UI", 9)).pack(fill="x", padx=6)
        tk.Button(self.sidebar, text="ⓘ  About / status", command=self.about, bg="#0d141d", fg=TEXT,
                  activebackground=PANEL_2, relief="flat", anchor="w", padx=16, pady=8, font=("Segoe UI", 9)).pack(fill="x", padx=6)
        tk.Button(self.sidebar, text="▦  Apps & Users", command=self.open_apps_users, bg="#0d141d", fg=ACCENT,
                  activebackground=PANEL_2, relief="flat", anchor="w", padx=16, pady=8, font=("Segoe UI", 9)).pack(fill="x", padx=6)
        tk.Button(self.sidebar, text="⇥  Sign out", command=self.sign_out, bg="#0d141d", fg=TEXT,
                  activebackground=PANEL_2, relief="flat", anchor="w", padx=16, pady=8, font=("Segoe UI", 9)).pack(fill="x", padx=6)
        self.workspace = tk.Frame(main, bg=BG)
        self.workspace.pack(side="left", fill="both", expand=True)
        self.desktop = tk.Frame(self.workspace, bg=BG)
        self.desktop.pack(fill="both", expand=True)
        self.desktop.bind("<Configure>", self._desktop_resize)
        self._create_wallpaper_surface()
        self._apply_saved_wallpaper()
        self.taskbar = tk.Frame(self.workspace, bg="#0c131c", height=43)
        self.taskbar.pack(fill="x", side="bottom")
        self.taskbar.pack_propagate(False)
        tk.Label(self.taskbar, text="  D  ", bg="#0c131c", fg=ACCENT, font=("Segoe UI", 12, "bold")).pack(side="left")
        self.task_buttons = tk.Frame(self.taskbar, bg="#0c131c")
        self.task_buttons.pack(side="left", fill="y")
        tk.Label(self.taskbar, text="LOCAL-FIRST  •  NO AUTO-ELEVATION", bg="#0c131c", fg=MUTED, font=("Consolas", 8)).pack(side="right", padx=15)

    def _create_wallpaper_surface(self):
        """Create a static blank-color desktop surface; animation is opt-in via a chosen GIF."""
        self.wallpaper_label = tk.Label(self.desktop, bg=self.wallpaper_color, bd=0, highlightthickness=0)
        self.wallpaper_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.wallpaper_label.lower()
        self.desktop.bind("<Configure>", self._resize_wallpaper, add="+")

    def open_wallpaper_menu(self):
        menu = tk.Menu(self.root, tearoff=False, bg=PANEL_2, fg=TEXT, activebackground=BORDER,
                       activeforeground=ACCENT)
        menu.add_command(label="Solid color…", command=self.choose_wallpaper_color)
        menu.add_command(label="Picture or GIF…", command=self.choose_wallpaper_image)
        menu.add_command(label="Reset to default", command=self.reset_wallpaper)
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def choose_wallpaper_color(self):
        chosen = colorchooser.askcolor(color=self.wallpaper_color, title="DILARA desktop color", parent=self.root)
        if chosen and chosen[1]:
            self.wallpaper_color = chosen[1]
            self.wallpaper_path = None
            self._stop_wallpaper_animation()
            self._render_wallpaper()
            self._persist_wallpaper()

    def choose_wallpaper_image(self):
        path = filedialog.askopenfilename(parent=self.root, title="Choose desktop wallpaper",
            filetypes=[("Pictures and GIFs", "*.png *.gif *.jpg *.jpeg *.bmp *.webp"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.wallpaper_path = str(Path(path).resolve())
            self._render_wallpaper()
            self._persist_wallpaper()
        except Exception as exc:
            self.wallpaper_path = None
            self._stop_wallpaper_animation()
            messagebox.showerror("Wallpaper", f"Could not load this image. For JPEG/WebP, install Pillow.\n\n{exc}", parent=self.root)
            self._render_wallpaper()

    def reset_wallpaper(self):
        self.wallpaper_color = BG
        self.wallpaper_path = None
        self._stop_wallpaper_animation()
        self._render_wallpaper()
        self._persist_wallpaper()

    def _persist_wallpaper(self):
        self.saved_state["wallpaper"] = {"color": self.wallpaper_color, "path": self.wallpaper_path}
        self._write_state_silently()

    def _apply_saved_wallpaper(self):
        wallpaper = self.saved_state.get("wallpaper", {}) if isinstance(self.saved_state, dict) else {}
        if isinstance(wallpaper, dict):
            self.wallpaper_color = wallpaper.get("color") or BG
            candidate = wallpaper.get("path")
            self.wallpaper_path = candidate if candidate and Path(candidate).is_file() else None
        self._render_wallpaper()

    def _stop_wallpaper_animation(self):
        if self._wallpaper_after_id is not None:
            try: self.root.after_cancel(self._wallpaper_after_id)
            except tk.TclError: pass
            self._wallpaper_after_id = None
        self._wallpaper_frames = []
        self._wallpaper_frame_index = 0
        self._wallpaper_pil = None

    def _resize_wallpaper(self, _event=None):
        if self.wallpaper_path and self._wallpaper_pil:
            if self._wallpaper_after_id is not None:
                try: self.root.after_cancel(self._wallpaper_after_id)
                except tk.TclError: pass
                self._wallpaper_after_id = None
            self._show_wallpaper_frame(self._wallpaper_frame_index)

    def _render_wallpaper(self, keep_animation=False):
        if not hasattr(self, "wallpaper_label") or not self.wallpaper_label.winfo_exists():
            return
        if not keep_animation:
            self._stop_wallpaper_animation()
        self.wallpaper_label.configure(bg=self.wallpaper_color, image="")
        self.wallpaper_label.image = None
        if not self.wallpaper_path:
            self.wallpaper_label.lower()
            return
        path = Path(self.wallpaper_path)
        try:
            from PIL import Image, ImageSequence, ImageTk
            image = Image.open(path)
            frames = [frame.copy().convert("RGB") for frame in ImageSequence.Iterator(image)] if path.suffix.lower() == ".gif" else [image.convert("RGB")]
            self._wallpaper_pil = frames
            self._wallpaper_frames = frames if len(frames) > 1 else []
            self._show_wallpaper_frame(0)
        except ImportError:
            # Tk can render GIF/PNG without Pillow; JPEG/WebP need Pillow.
            if path.suffix.lower() not in {".gif", ".png", ".ppm", ".pgm"}:
                raise RuntimeError("Pillow is required for this image format. Install it with: py -m pip install Pillow")
            photo = tk.PhotoImage(file=str(path))
            self.wallpaper_label.configure(image=photo)
            self.wallpaper_label.image = photo
            self.wallpaper_label.lower()
        except Exception:
            raise

    def _show_wallpaper_frame(self, index):
        if not self._wallpaper_pil:
            return
        try:
            from PIL import Image, ImageTk
            frame = self._wallpaper_pil[index % len(self._wallpaper_pil)]
            w, h = max(1, self.desktop.winfo_width()), max(1, self.desktop.winfo_height())
            # Fill the desktop while preserving aspect ratio, then crop center.
            scale = max(w / frame.width, h / frame.height)
            resized = frame.resize((max(1, int(frame.width * scale)), max(1, int(frame.height * scale))), Image.Resampling.LANCZOS)
            left, top = (resized.width - w) // 2, (resized.height - h) // 2
            resized = resized.crop((left, top, left + w, top + h))
            photo = ImageTk.PhotoImage(resized)
            self.wallpaper_label.configure(image=photo)
            self.wallpaper_label.image = photo
            self.wallpaper_label.lower()
            self._wallpaper_frame_index = index % len(self._wallpaper_pil)
            if self._wallpaper_frames and self.root.winfo_exists():
                duration = 100
                try:
                    from PIL import Image
                    duration = max(40, int(self._wallpaper_pil[index % len(self._wallpaper_pil)].info.get("duration", 100)))
                except Exception: pass
                self._wallpaper_after_id = self.root.after(duration, lambda: self._show_wallpaper_frame(index + 1))
        except tk.TclError:
            return

    def _desktop_resize(self, _event=None):
        for win in self.windows.values():
            if win.maximized and not win.minimized:
                win.w = max(360, self.desktop.winfo_width()-24)
                win.h = max(240, self.desktop.winfo_height()-24)
                win.frame.place_configure(width=win.w, height=win.h)

    def open_module(self, key: str, restoring=False):
        module = next(m for m in MODULES if m[0] == key)
        if key in self.windows:
            self.windows[key].restore()
            return
        count = len(self.windows)
        x = 50 + (count * 34) % max(100, self.desktop.winfo_width() - 650)
        y = 35 + (count * 28) % max(80, self.desktop.winfo_height() - 430)
        default_w, default_h = (650, 700) if key == "D-LLM" else (760, 520) if key in {"D-TERMINAL", "NOTEPAD", "STACK"} else (560, 360)
        default_w = min(default_w, max(420, self.desktop.winfo_width() - 30))
        default_h = min(default_h, max(300, self.desktop.winfo_height() - 30))
        self.windows[key] = DesktopWindow(self, module, x, y, default_w, default_h, restoring=restoring)
        self._record_activity("module_opened", key)
        self.refresh_taskbar()

    def _record_activity(self, event: str, module: str):
        try:
            self.activity_logger.record(event, module)
        except ActivityLogError as exc:
            # Never fall back to plaintext activity logging. Keep the shell usable.
            print(f"[DILARA activity log] {exc}", file=sys.stderr)

    def build_workspace(self, win: DesktopWindow):
        """Build functional first-pass workspaces while keeping the shell window manager shared."""
        key = win.key
        body = win.body
        tk.Label(body, text=key, bg=PANEL, fg=ACCENT, font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(body, text=win.subtitle.upper(), bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(1, 10))
        if key in {"DSPACE", "CYBERSTORM", "EYE"}:
            self._build_resource_workspace(win)
        elif key == "D-ARCADE":
            self._build_arcade_workspace(win)
        elif key == "D-LLM":
            self._build_llm_workspace(win)
        elif key == "D-TERMINAL":
            self._build_terminal_workspace(win)
        elif key == "CHAOS":
            self._build_chaos_workspace(win)
        elif key == "BROWSER":
            self._build_browser_workspace(win)
        elif key == "FILES":
            self._build_files_workspace(win)
        elif key == "NOTEPAD":
            self._build_notepad_workspace(win)
        elif key == "KOD8":
            self._build_kod8_workspace(win)

    def _build_browser_workspace(self, win):
        body = win.body
        tk.Label(body, text="DILARA BROWSER // EMBEDDED WEB WORKSPACE", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(body, text="The Chromium-based PyQt browser is hosted inside this DILARA workspace on Windows. D-LLM and D-ARCADE remain separate class applications.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=650, justify="left").pack(anchor="w", pady=(4, 8))
        status = tk.Label(body, text="STATUS  •  Preparing embedded browser…", bg=PANEL, fg=MUTED,
                          font=("Consolas", 8), anchor="w")
        status.pack(fill="x", pady=(0, 6))
        host = tk.Frame(body, bg="#05080d", highlightbackground=BORDER, highlightthickness=1)
        host.pack(fill="both", expand=True)
        host.bind("<Configure>", lambda _e: self._resize_embedded_browser(host), add="+")

        def launch():
            if self.browser_adapter.is_running():
                status.configure(text="STATUS  •  Reattaching existing browser window…", fg=WARN)
                self._embed_browser_window(host, self.browser_adapter.process, status, attempts=0)
                return
            try:
                process = self.browser_adapter.launch(None)
                self.browser_owner = getattr(win, "_stack_parent", win)
                status.configure(text="STATUS  •  Starting browser engine…", fg=WARN)
                self._record_activity("browser_launched", "BROWSER")
                if sys.platform == "win32":
                    self.root.after(180, lambda: self._embed_browser_window(host, process, status, attempts=0))
                else:
                    status.configure(text="STATUS  •  Browser launched as a separate process (native embedding requires Windows).", fg=WARN)
            except (OSError, FileNotFoundError, RuntimeError) as exc:
                status.configure(text=f"STATUS  •  Launch failed: {exc}", fg=WARN)
                messagebox.showerror("DILARA Browser", f"Could not launch the browser:\n{exc}", parent=win.frame)

        controls = tk.Frame(body, bg=PANEL); controls.pack(fill="x", pady=(0, 6))
        tk.Button(controls, text="Start / Reattach Browser", command=launch, bg=PANEL_2,
                  fg=ACCENT, activebackground=BORDER, relief="flat", padx=10, pady=5,
                  font=("Segoe UI Semibold", 9), cursor="hand2").pack(anchor="w")
        tk.Label(body, text="Downloads remain blocked and browser profile/history data stays separate per DILARA user. Closing this workspace closes its browser process.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=650, justify="left").pack(anchor="w", pady=(6, 0))
        if not getattr(win, "restoring", False):
            self.root.after(250, launch)

    def _embed_browser_window(self, host, process, status, attempts=0):
        if not host.winfo_exists() or process is None or process.poll() is not None:
            if host.winfo_exists(): status.configure(text="STATUS  •  Browser process exited before embedding", fg=WARN)
            return
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
            user32.SetParent.restype = wintypes.HWND
            user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
            user32.SetWindowLongW.restype = ctypes.c_long
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            user32.SetWindowPos.restype = wintypes.BOOL
            target = {"hwnd": None}
            enum_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def enum_callback(hwnd, _lparam):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == process.pid and user32.IsWindowVisible(hwnd) and user32.GetWindow(hwnd, 4) == 0:
                    target["hwnd"] = hwnd
                    return False
                return True
            user32.EnumWindows(enum_type(enum_callback), 0)
            hwnd = target["hwnd"]
            if not hwnd:
                if attempts < 60:
                    self.root.after(150, lambda: self._embed_browser_window(host, process, status, attempts + 1))
                else:
                    status.configure(text="STATUS  •  Browser opened but its native window could not be embedded", fg=WARN)
                return
            GWL_STYLE = -16
            WS_CHILD, WS_VISIBLE = 0x40000000, 0x10000000
            WS_POPUP, WS_CAPTION, WS_THICKFRAME = 0x80000000, 0x00C00000, 0x00040000
            WS_MINIMIZEBOX, WS_MAXIMIZEBOX, WS_SYSMENU = 0x00020000, 0x00010000, 0x00080000
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style = (style & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)) | WS_CHILD | WS_VISIBLE
            user32.SetParent(hwnd, host.winfo_id())
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            self._embedded_browser_hwnd = hwnd
            self._embedded_browser_host = host
            self._resize_embedded_browser(host)
            status.configure(text="STATUS  •  Browser embedded and ready", fg=ACCENT)
        except Exception as exc:
            status.configure(text=f"STATUS  •  Native embedding failed: {exc}", fg=WARN)

    def _resize_embedded_browser(self, host):
        hwnd = getattr(self, "_embedded_browser_hwnd", None)
        if not hwnd or not host.winfo_exists() or sys.platform != "win32":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            from ctypes import wintypes
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            user32.SetWindowPos.restype = wintypes.BOOL
            user32.SetWindowPos(hwnd, 0, 0, 0, max(1, host.winfo_width()), max(1, host.winfo_height()),
                                0x0004 | 0x0010 | 0x0020)  # NOZORDER | NOACTIVATE | FRAMECHANGED
        except Exception:
            pass

    def _build_kod8_workspace(self, win):
        body = win.body
        tk.Label(body, text="KOD8 // CRYPTOGRAPHIC WORKSPACE", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(body, text="The original CL1–CL8 source and standalone UI are preserved. This tab is a launcher/status surface; the existing KOD8 UI remains a separate process.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=650, justify="left").pack(anchor="w", pady=(6, 12))
        tk.Button(body, text="Launch KOD8 side application", command=self.launch_kod8_side_app,
                  bg=ACCENT, fg="#071014", relief="flat", padx=12, pady=7).pack(anchor="w")
        tk.Label(body, text="Security note: the current experimental transforms do not provide authenticated encryption or tamper detection.",
                 bg=PANEL, fg=WARN, font=("Segoe UI", 8), wraplength=650, justify="left").pack(anchor="w", pady=(10, 0))

    def _build_notepad_workspace(self, win):
        body = win.body
        top = tk.Frame(body, bg=PANEL); top.pack(fill="x")
        current = {"path": None, "dirty": False}
        path_label = tk.Label(top, text="Untitled.txt", bg=PANEL, fg=ACCENT, font=("Consolas", 9), anchor="w")
        path_label.pack(side="left", fill="x", expand=True)
        editor = tk.Text(body, bg="#070c12", fg=TEXT, insertbackground=TEXT, selectbackground="#24434a",
                         undo=True, wrap="word", relief="flat", font=("Consolas", 10), padx=10, pady=10)
        editor.pack(fill="both", expand=True, pady=(8, 0))

        def mark_dirty(_event=None):
            current["dirty"] = True
            name = Path(current["path"]).name if current["path"] else "Untitled.txt"
            path_label.configure(text=f"● {name}")
        editor.bind("<<Modified>>", lambda _e: (editor.edit_modified(False), mark_dirty()) if editor.edit_modified() else None)

        def maybe_save():
            if not current["dirty"]: return True
            answer = messagebox.askyesnocancel("Notepad", "Save changes before continuing?", parent=win.frame)
            if answer is None: return False
            if answer: return save_as_or_current()
            return True

        def load_path(path):
            try: content = Path(path).read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                messagebox.showwarning("Notepad", "This file is not UTF-8 text.", parent=win.frame); return
            except OSError as exc:
                messagebox.showerror("Notepad", f"Could not open file: {exc}", parent=win.frame); return
            editor.delete("1.0", "end"); editor.insert("1.0", content)
            current["path"] = str(Path(path).resolve()); current["dirty"] = False
            path_label.configure(text=Path(path).name); editor.edit_modified(False)

        def new_file():
            if not maybe_save(): return
            editor.delete("1.0", "end"); current.update(path=None, dirty=False)
            path_label.configure(text="Untitled.txt"); editor.edit_modified(False)

        def open_file():
            if not maybe_save(): return
            path = filedialog.askopenfilename(parent=win.frame, title="Open text file", filetypes=[("Text files", "*.txt *.md *.log *.json *.py *.ps1 *.ini *.csv"), ("All files", "*.*")])
            if path: load_path(path)

        def save_as_or_current(force_dialog=False):
            path = current["path"]
            if force_dialog or not path:
                path = filedialog.asksaveasfilename(parent=win.frame, title="Save text file", defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")], initialfile=Path(path).name if path else "Untitled.txt")
                if not path: return False
            try:
                target = Path(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_name(target.name + ".tmp")
                temp.write_text(editor.get("1.0", "end-1c"), encoding="utf-8", newline="")
                os.replace(temp, target)
                current["path"] = str(target.resolve()); current["dirty"] = False
                path_label.configure(text=target.name); editor.edit_modified(False)
                return True
            except OSError as exc:
                messagebox.showerror("Notepad", f"Save failed: {exc}", parent=win.frame); return False

        for label, callback in (("New", new_file), ("Open…", open_file), ("Save", lambda: save_as_or_current()), ("Save as…", lambda: save_as_or_current(True))):
            tk.Button(top, text=label, command=callback, bg=PANEL_2, fg=TEXT, activebackground=BORDER,
                      relief="flat", padx=8, pady=4).pack(side="left", padx=(4, 0))
        editor.focus_set()

    def open_stacked_workspace(self):
        # LLM and Arcade remain class workspaces because their legacy applications are separate processes.
        compatible = [m for m in MODULES if m[0] not in {"STACK", "D-LLM", "D-ARCADE"}]
        dialog = tk.Toplevel(self.root); dialog.title("Create stacked workspace"); dialog.geometry("390x540")
        dialog.configure(bg=BG); dialog.transient(self.root)
        tk.Label(dialog, text="STACKED WORKSPACE", bg=BG, fg=ACCENT, font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(16, 5))
        tk.Label(dialog, text="Choose compatible modules to combine as tabs in one desktop window. D-LLM and D-ARCADE remain separate class applications; KOD8 opens its preserved side UI from a tab.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=350, justify="left").pack(anchor="w", padx=16, pady=(0, 10))
        checks = {}
        container = tk.Frame(dialog, bg=BG); container.pack(fill="both", expand=True, padx=14)
        for key, subtitle, desc in compatible:
            value = tk.BooleanVar(value=key in {"NOTEPAD", "D-TERMINAL"})
            checks[key] = value
            tk.Checkbutton(container, text=f"{key}  —  {subtitle}", variable=value, bg=BG, fg=TEXT,
                selectcolor=PANEL_2, activebackground=BG, activeforeground=ACCENT, anchor="w").pack(fill="x", pady=2)
        def create():
            keys = [key for key, var in checks.items() if var.get()]
            if not keys:
                messagebox.showinfo("Stacked workspace", "Select at least one module.", parent=dialog); return
            dialog.destroy()
            self._create_stacked_window(keys)
        tk.Button(dialog, text="Create workspace", command=create, bg=ACCENT, fg="#071014", relief="flat", padx=14, pady=8).pack(anchor="e", padx=16, pady=14)

    def _create_stacked_window(self, keys, restoring=False):
        title = " + ".join(keys[:3]) + (f" +{len(keys)-3}" if len(keys) > 3 else "")
        module = ("STACK", title, "Tabbed class workspace")
        if "STACK" in self.windows:
            self.windows["STACK"].close()
        w = min(920, max(620, self.desktop.winfo_width() - 30))
        h = min(700, max(400, self.desktop.winfo_height() - 30))
        win = DesktopWindow(self, module, 24, 20, w, h, stack_keys=keys, restoring=restoring)
        self.windows["STACK"] = win
        self._record_activity("stacked_workspace_opened", "STACK")
        self.refresh_taskbar()

    def build_stacked_workspace(self, win):
        tabs = ttk.Notebook(win.body)
        tabs.pack(fill="both", expand=True)
        win._stack_proxies = []
        for key in win.stack_keys:
            module = next((item for item in MODULES if item[0] == key), None)
            if not module or key in {"STACK", "D-LLM", "D-ARCADE"}:
                continue
            tab = tk.Frame(tabs, bg=PANEL, padx=12, pady=10)
            tabs.add(tab, text=key)
            proxy = type("WorkspaceProxy", (), {})()
            proxy.app = self; proxy.module = module; proxy.key = key; proxy.subtitle = module[1]
            proxy.description = module[2]; proxy.body = tab; proxy.frame = win.frame; proxy._stack_parent = win; proxy.restoring = win.restoring
            win._stack_proxies.append(proxy)
            self.build_workspace(proxy)
        if not win._stack_proxies:
            tk.Label(win.body, text="No compatible modules selected.", bg=PANEL, fg=MUTED).pack()

    def _build_files_workspace(self, win):
        """Small tree-based UI backed by the currently unlocked per-user vault."""
        from tkinter import simpledialog
        body = win.body
        root_path = self.vault.root
        if root_path is None:
            tk.Label(body, text="VAULT IS LOCKED", bg=PANEL, fg=WARN).pack(anchor="w")
            return
        tk.Label(body, text="VIRTUAL ROOT  /  ENCRYPTED USER VAULT", bg=PANEL, fg=MUTED,
                 font=("Consolas", 8)).pack(anchor="w", pady=(0, 8))
        path_label = tk.Label(body, text="/", bg=PANEL, fg=ACCENT, font=("Consolas", 9), anchor="w")
        path_label.pack(fill="x", pady=(0, 7))
        tree_frame = tk.Frame(body, bg=PANEL)
        tree_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(tree_frame, columns=("kind", "size"), show="tree headings", selectmode="browse")
        tree.heading("#0", text="Name", anchor="w")
        tree.heading("kind", text="Type", anchor="w")
        tree.heading("size", text="Size", anchor="e")
        tree.column("#0", width=270, stretch=True)
        tree.column("kind", width=90, stretch=False)
        tree.column("size", width=80, stretch=False, anchor="e")
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        paths = {}

        def safe_inside(path):
            resolved = Path(path).resolve()
            if not resolved.is_relative_to(root_path.resolve()):
                raise ValueError("That path is outside the current user's virtual root.")
            return resolved

        def refresh(select_path=None):
            for item in tree.get_children():
                tree.delete(item)
            paths.clear()
            path_label.configure(text="/  (user root)")
            def add_directory(folder, parent_iid=""):
                try:
                    children = sorted(folder.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))
                except OSError:
                    return
                for child in children:
                    if child.is_symlink():
                        continue
                    try:
                        child = safe_inside(child)
                    except ValueError:
                        continue
                    is_dir = child.is_dir()
                    size = "—" if is_dir else _format_file_size(child.stat().st_size)
                    iid = f"node{len(paths)}"
                    paths[iid] = child
                    tree.insert(parent_iid, "end", iid=iid, text=("▸  " if is_dir else "   ") + child.name,
                                values=("Folder" if is_dir else child.suffix.lower() or "File", size),
                                open=(parent_iid == ""))
                    if is_dir:
                        add_directory(child, iid)
            add_directory(root_path)
            if select_path:
                for iid, path in paths.items():
                    if path == select_path:
                        tree.selection_set(iid); tree.see(iid); break

        def selected_path():
            selected = tree.selection()
            if not selected:
                return root_path
            return paths.get(selected[0], root_path)

        def target_directory():
            path = selected_path()
            return path if path.is_dir() else path.parent

        def new_folder():
            parent = target_directory()
            name = simpledialog.askstring("Create folder", "Folder name:", parent=win.frame)
            if not name:
                return
            if name in {".", ".."} or "/" in name or "\\" in name or Path(name).name != name:
                messagebox.showwarning("Files", "Enter a single folder name, not a path.", parent=win.frame); return
            try:
                destination = safe_inside(parent / name)
                destination.mkdir()
                refresh(destination)
            except FileExistsError:
                messagebox.showwarning("Files", "An item with that name already exists.", parent=win.frame)
            except (OSError, ValueError) as exc:
                messagebox.showerror("Files", str(exc), parent=win.frame)

        def edit_file(path, initial_text=None):
            try:
                path = safe_inside(path)
                content = path.read_text(encoding="utf-8") if initial_text is None else initial_text
            except UnicodeDecodeError:
                messagebox.showwarning("Files", "This file is not UTF-8 text and cannot be opened in the built-in editor.", parent=win.frame); return
            except OSError as exc:
                messagebox.showerror("Files", f"Could not open file: {exc}", parent=win.frame); return
            editor = tk.Toplevel(self.root)
            editor.title(f"DILARA Notepad // {path.name}")
            editor.geometry("760x560")
            editor.configure(bg=BG)
            editor.transient(self.root)
            header = tk.Frame(editor, bg=PANEL_2, padx=12, pady=8); header.pack(fill="x")
            tk.Label(header, text=str(path.relative_to(root_path)).replace("\\", "/"), bg=PANEL_2, fg=ACCENT,
                     font=("Consolas", 9)).pack(side="left")
            text_widget = tk.Text(editor, bg="#080d13", fg=TEXT, insertbackground=TEXT, wrap="none",
                                  undo=True, relief="flat", font=("Consolas", 10))
            text_widget.pack(fill="both", expand=True, padx=8, pady=8)
            text_widget.insert("1.0", content)
            def save():
                try:
                    checked = safe_inside(path)
                    temp = checked.with_name(checked.name + ".tmp")
                    temp.write_text(text_widget.get("1.0", "end-1c"), encoding="utf-8")
                    os.replace(temp, checked)
                    refresh(checked)
                    messagebox.showinfo("Notepad", "Saved to the unlocked user vault workspace.", parent=editor)
                except (OSError, ValueError) as exc:
                    messagebox.showerror("Notepad", f"Save failed: {exc}", parent=editor)
            tk.Button(header, text="Save", command=save, bg=ACCENT, fg="#071014", relief="flat", padx=12).pack(side="right")
            editor.grab_set()
            editor.focus_set()

        def new_text():
            parent = target_directory()
            name = simpledialog.askstring("New text file", "File name (extension optional):", parent=win.frame)
            if not name:
                return
            if name in {".", ".."} or "/" in name or "\\" in name or Path(name).name != name:
                messagebox.showwarning("Files", "Enter a single file name, not a path.", parent=win.frame); return
            if not Path(name).suffix:
                name += ".txt"
            try:
                destination = safe_inside(parent / name)
                with destination.open("x", encoding="utf-8") as handle:
                    handle.write("")
                refresh(destination)
                edit_file(destination, "")
            except FileExistsError:
                messagebox.showwarning("Files", "An item with that name already exists.", parent=win.frame)
            except (OSError, ValueError) as exc:
                messagebox.showerror("Files", str(exc), parent=win.frame)

        def open_selected(_event=None):
            path = selected_path()
            if path.is_dir():
                try:
                    path_label.configure(text="/" + path.relative_to(root_path).as_posix().strip("."))
                except ValueError:
                    path_label.configure(text="/")
                return
            edit_file(path)

        actions = tk.Frame(body, bg=PANEL); actions.pack(fill="x", pady=(8, 0))
        for label, command in (("New folder", new_folder), ("New text file", new_text), ("Open / edit", open_selected), ("Refresh", lambda: refresh())):
            tk.Button(actions, text=label, command=command, bg=PANEL_2, fg=TEXT, activebackground=BORDER,
                      relief="flat", padx=9, pady=6, font=("Segoe UI", 8), cursor="hand2").pack(side="left", padx=(0, 5))
        tree.bind("<Double-1>", open_selected)
        refresh()
        tk.Label(body, text="Files are staged in the active session and encrypted into the user's .dvault container when signing out. Do not force-close DILARA while files are being saved.",
                 bg=PANEL, fg=WARN, font=("Segoe UI", 8), wraplength=500, justify="left").pack(anchor="w", pady=(8, 0))

    def _build_resource_workspace(self, win):
        key = win.key
        body = win.body
        tk.Label(body, text=win.description, bg=PANEL, fg=TEXT, font=("Segoe UI", 9), wraplength=490, justify="left").pack(anchor="w", pady=(0, 8))
        toolbar = tk.Frame(body, bg=PANEL); toolbar.pack(fill="x", pady=(0, 8))
        tk.Label(toolbar, text="Country / region", bg=PANEL, fg=MUTED).pack(side="left")
        country = tk.Entry(toolbar, bg="#0a1119", fg=TEXT, insertbackground=TEXT, relief="flat", width=18)
        country.pack(side="left", padx=6)
        country.insert(0, "Global")
        tk.Label(toolbar, text="Label", bg=PANEL, fg=MUTED).pack(side="left", padx=(6, 0))
        label = tk.Entry(toolbar, bg="#0a1119", fg=TEXT, insertbackground=TEXT, relief="flat", width=18)
        label.pack(side="left", padx=6)
        field_label = "Camera stream URL" if key == "EYE" else ("FTP URL" if key == "CYBERSTORM" else "URL")
        tk.Label(body, text=field_label, bg=PANEL, fg=MUTED).pack(anchor="w")
        url = tk.Entry(body, bg="#0a1119", fg=TEXT, insertbackground=TEXT, relief="flat")
        url.pack(fill="x", pady=(3, 8), ipady=5)
        list_frame = tk.Frame(body, bg=PANEL); list_frame.pack(fill="both", expand=True)
        columns = ("country", "label", "url")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=7)
        for col, title, width in [("country", "COUNTRY", 100), ("label", "LOCATION / NAME", 150), ("url", "ADDRESS", 260)]:
            tree.heading(col, text=title); tree.column(col, width=width, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview); scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)
        store_path = self.user_dir / "resources" / ("cameras.json" if key == "EYE" else "ftp_resources.json" if key == "CYBERSTORM" else "dspace_resources.json")
        def read_items():
            try:
                raw = json.loads(store_path.read_text(encoding="utf-8"))
                return raw if isinstance(raw, list) else []
            except (OSError, json.JSONDecodeError): return []
        items = read_items()
        def refresh():
            tree.delete(*tree.get_children())
            for i, item in enumerate(items): tree.insert("", "end", iid=str(i), values=(item.get("country", ""), item.get("label", ""), item.get("url", "")))
        def save():
            store_path.parent.mkdir(parents=True, exist_ok=True)
            store_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        def add_item():
            c, l, u = country.get().strip(), label.get().strip(), url.get().strip()
            if not c or not l or not u.startswith(("http://", "https://", "ftp://", "ftps://", "rtsp://")):
                messagebox.showwarning(key, "Enter a country, a label, and a URL beginning with http://, https://, ftp://, ftps://, or rtsp://.")
                return
            items.append({"country": c, "label": l, "url": u}); save(); refresh(); label.delete(0, "end"); url.delete(0, "end")
            self._record_activity("resource_added", key)
        def remove_item():
            selected = tree.selection()
            if not selected: return
            idx = int(selected[0])
            if 0 <= idx < len(items): items.pop(idx); save(); refresh()
        actions = tk.Frame(body, bg=PANEL); actions.pack(fill="x", pady=(8, 0))
        tk.Button(actions, text="Add entry", command=add_item, bg=ACCENT, fg="#071014", relief="flat", padx=10).pack(side="left")
        tk.Button(actions, text="Remove selected", command=remove_item, bg=PANEL_2, fg=TEXT, relief="flat", padx=10).pack(side="left", padx=6)
        def open_selected(_event=None):
            sel=tree.selection()
            if not sel: return
            item=items[int(sel[0])]
            if key == "EYE":
                try: subprocess.Popen(["cmd", "/c", "start", "", item["url"]], shell=False)
                except OSError as exc: messagebox.showerror(key, str(exc))
                self._record_activity("camera_stream_opened", key)
            else:
                import webbrowser
                webbrowser.open(item["url"])
                self._record_activity("resource_opened", key)
        tree.bind("<Double-1>", open_selected)
        tk.Label(body, text="Double-click an entry to open it. EYE launches streams in the system handler; this first pass does not decode/embed video.", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=490, justify="left").pack(anchor="w", pady=(5, 0))
        refresh()

    def _build_arcade_workspace(self, win):
        body=win.body
        tk.Label(body, text="GAME LIBRARY", bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(body, text="Be wary.. Couple games might have different variations", bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=490, justify="left").pack(anchor="w", pady=(4, 12))
        base=APP_DIR / "legacy_modules" / "D-ARCADE CLASS"
        games=[
            ("Chess 1", base/"D-ARCADE-CHESS-main"/"chess_gui.py", "pillow"),
            ("Chess 2", base/"D-ARCADE-CHESS-main"/"chess_gui_v2.py", "pillow"),            
            ("Tetris", base/"D-ARCADE-TETRIS-main"/"D-ARCADE-TETRIS.py", "pygame"),
            ("Lightcycle", base/"D-ARCADE-Trolightcycle-main"/"D-ARCADE-Tron-Lightcycle.py", "pygame"),
            ("Maze 1", base/"D-ARCADE-MAZE-DEMO"/"D-ARCADE_MAZEGPT.py", "tkinter / source-dependent"),
            ("Maze 2", base/"D-ARCADE-MAZE-DEMO"/"D-ARCADE_MAZEGEMİNİ.py", "tkinter / source-dependent"),
            ("Maze 3", base/"D-ARCADE-MAZE-DEMO"/"D-ARCADE_MAZEGEMİNİ2.py", "tkinter / source-dependent"),
            ("Tic-tac-toe 1", base/"magenta-tictactoe-main"/"magenta-tic-tac-toe.py", "console"),
            ("Tic-tac-toe 2", base/"magenta-tictactoe-main"/"tic-tac-toe.py", "console"),
        ]
        for name, path, note in games:
            row=tk.Frame(body,bg=PANEL_2,padx=10,pady=7); row.pack(fill="x",pady=3)
            tk.Label(row,text=name,bg=PANEL_2,fg=TEXT,font=("Segoe UI",10,"bold")).pack(side="left")
            tk.Label(row,text=note,bg=PANEL_2,fg=MUTED,font=("Segoe UI",8)).pack(side="left",padx=10)
            tk.Button(row,text="Launch",command=lambda n=name,p=path:self.launch_legacy_game(n,p),bg=ACCENT,fg="#071014",relief="flat",padx=12).pack(side="right")
        tk.Label(body,text="Legacy dependencies (Pillow / Pygame) must be installed in the Python environment you use to launch DILARA. The maze and console game require additional compatibility testing.",bg=PANEL,fg=WARN,font=("Segoe UI",8),wraplength=490,justify="left").pack(anchor="w",pady=(10,0))

    def launch_legacy_game(self, name, path):
        if not path.is_file():
            messagebox.showerror("D-ARCADE", f"Game source not found:\n{path}"); return
        try:
            proc=subprocess.Popen([sys.executable, str(path)], cwd=str(path.parent))
            self._record_activity("game_launched", "D-ARCADE")
            self._record_activity("side_process_started", "D-ARCADE")
        except OSError as exc: messagebox.showerror("D-ARCADE", f"Could not launch {name}:\n{exc}")

    def _build_llm_workspace(self, win):
        body = win.body
        tk.Label(body, text="D-LLM // CUSTOM CHATBOT WORKSPACE", bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(body, text="D-LLM is the in-house chatbot/rough LLM project under active development. It does not require Ollama, a pulled model, GGUF weights, or a separate inference runtime. The legacy v2 Ollama experiment is preserved for reference only and is not offered as the D-LLM launch path.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=490, justify="left").pack(anchor="w", pady=(5, 10))
        custom = tk.Frame(body, bg=PANEL_2, padx=12, pady=10); custom.pack(fill="x", pady=4)
        tk.Label(custom, text="01  DILARA CORE // WORK IN PROGRESS", bg=PANEL_2, fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(custom, text="Launch the original dilara_core.py chatbot UI. This is the unfinished custom implementation, not the separate Ollama-based v2 branch. Optional voice features have different network behavior: Vosk can work offline when its local model is installed; SpeechRecognition's Google fallback uses the network.", bg=PANEL_2, fg=TEXT, font=("Segoe UI", 9), wraplength=440, justify="left").pack(anchor="w", pady=4)
        tk.Button(custom, text="Launch Custom D-LLM", command=self.launch_custom_dllm, bg=ACCENT, fg="#071014", relief="flat", padx=12, pady=6).pack(anchor="w", pady=(4, 0))
        fallback = tk.Frame(body, bg=PANEL_2, padx=12, pady=10); fallback.pack(fill="x", pady=4)
        tk.Label(fallback, text="02  BUILT-IN UTILITY FALLBACK", bg=PANEL_2, fg=ACCENT_2, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(fallback, text="A minimal no-network helper for DILARA help and basic calculations. It is not a generative language model; use it when you need a lightweight fallback.", bg=PANEL_2, fg=TEXT, font=("Segoe UI", 9), wraplength=440, justify="left").pack(anchor="w", pady=4)
        tk.Button(fallback, text="Open utility fallback", command=self.open_offline_chat, bg="#2b3544", fg=TEXT, relief="flat", padx=10, pady=6).pack(anchor="w", pady=(4, 0))
        app_heading = tk.Frame(body, bg=PANEL); app_heading.pack(fill="x", pady=(12, 5))
        tk.Label(app_heading, text="AVAILABLE APPS", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")
        app_list = tk.Frame(body, bg=PANEL); app_list.pack(fill="x")
        def refresh_app_list():
            for child in app_list.winfo_children(): child.destroy()
            for app_key, app_name, _desc in MODULES:
                if app_key == "STACK": continue
                tk.Button(app_list, text=f"{app_key}  ·  {app_name}", command=lambda k=app_key: self.open_module(k), bg="#0d141d", fg=TEXT, activebackground=PANEL_2, activeforeground=ACCENT, relief="flat", anchor="w", padx=9, pady=4).pack(fill="x", pady=1)
            extra = [a for a in self.app_registry.list_apps() if a.get("enabled", True)]
            for item in extra:
                tk.Button(app_list, text=f"{item.get('name')}  ·  added app", command=lambda a=item: self.launch_registered_app(a), bg="#0d141d", fg=ACCENT_2, activebackground=PANEL_2, relief="flat", anchor="w", padx=9, pady=4).pack(fill="x", pady=1)
        tk.Button(app_heading, text="Refresh", command=refresh_app_list, bg=PANEL_2, fg=TEXT, relief="flat", padx=8, pady=2).pack(side="right")
        refresh_app_list()

    def launch_custom_dllm(self):
        core = APP_DIR / "legacy_modules" / "DilaraLLM_demo-main" / "dilara_core.py"
        if not core.is_file():
            messagebox.showerror("D-LLM", f"Custom D-LLM source not found:\n{core}")
            return
        if not messagebox.askyesno("Launch Custom D-LLM", "Launch the original in-progress dilara_core.py chatbot as a separate process?\n\nThe core UI is preserved as-is. Optional speech recognition may use Google's online service if the local Vosk path is unavailable."):
            return
        try:
            subprocess.Popen([sys.executable, str(core)], cwd=str(core.parent))
            self._record_activity("custom_dllm_launched", "D-LLM")
        except OSError as exc:
            messagebox.showerror("D-LLM", f"Could not launch custom D-LLM:\n{exc}")

    def open_offline_chat(self):
        top = tk.Toplevel(self.root); top.title("D-LLM // Offline Assistant"); top.geometry("650x520"); top.configure(bg=BG)
        tk.Label(top, text="D-LLM / OFFLINE ASSISTANT", bg=BG, fg=ACCENT, font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 5))
        tk.Label(top, text="No network calls. This built-in utility assistant does not include generative model weights.", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 8))
        transcript = tk.Text(top, bg="#0a1119", fg=TEXT, insertbackground=TEXT, wrap="word", relief="flat", padx=10, pady=10, state="disabled")
        transcript.pack(fill="both", expand=True, padx=16, pady=4)
        entryrow = tk.Frame(top, bg=BG); entryrow.pack(fill="x", padx=16, pady=(8, 14))
        entry = tk.Entry(entryrow, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat"); entry.pack(side="left", fill="x", expand=True, ipady=8)
        def send(_event=None):
            prompt = entry.get().strip()
            if not prompt: return
            answer = offline_respond(prompt)
            transcript.configure(state="normal"); transcript.insert("end", f"\nYOU  › {prompt}\nD-LLM › {answer}\n"); transcript.see("end"); transcript.configure(state="disabled")
            entry.delete(0, "end"); self._record_activity("offline_assistant_message", "D-LLM")
        tk.Button(entryrow, text="Send", command=send, bg=ACCENT, fg="#071014", relief="flat", padx=14).pack(side="left", padx=(8, 0))
        entry.bind("<Return>", send); entry.focus_set()
        transcript.configure(state="normal"); transcript.insert("end", "D-LLM offline mode ready. Type /help to begin.\n"); transcript.configure(state="disabled")

    def _build_terminal_workspace(self, win):
        body = win.body
        tk.Label(body, text="POWERSHELL // EMBEDDED SESSION", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(body, text="A dedicated standard-user PowerShell process is attached to this workspace. Commands execute locally; DILARA does not auto-elevate.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=650, justify="left").pack(anchor="w", pady=(4, 8))
        toolbar = tk.Frame(body, bg=PANEL); toolbar.pack(fill="x", pady=(0, 6))
        status = tk.Label(toolbar, text="SESSION NOT STARTED", bg=PANEL, fg=WARN, font=("Consolas", 8))
        status.pack(side="left")
        output = tk.Text(body, bg="#060a0f", fg="#c8f7e9", insertbackground=TEXT, relief="flat",
                         font=("Consolas", 9), wrap="word", undo=False, state="disabled")
        output.pack(fill="both", expand=True)
        entry_row = tk.Frame(body, bg=PANEL); entry_row.pack(fill="x", pady=(7, 0))
        tk.Label(entry_row, text="PS>", bg=PANEL, fg=ACCENT, font=("Consolas", 10, "bold")).pack(side="left", padx=(0, 7))
        command = tk.Entry(entry_row, bg="#0a1119", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", 10))
        command.pack(side="left", fill="x", expand=True, ipady=7)
        session_key = id(win)
        self.terminal_sessions[session_key] = {"process": None, "queue": queue.Queue(), "output": output, "status": status, "owner": win}
        self._terminal_owner[session_key] = getattr(win, "_stack_parent", win)

        def append(text):
            if not output.winfo_exists(): return
            output.configure(state="normal"); output.insert("end", text); output.see("end"); output.configure(state="disabled")

        def start_session():
            session = self.terminal_sessions[session_key]
            if session["process"] and session["process"].poll() is None:
                status.configure(text="SESSION ACTIVE", fg=ACCENT); command.focus_set(); return
            if sys.platform != "win32":
                status.configure(text="WINDOWS ONLY", fg=WARN)
                append("D-TERMINAL requires Windows PowerShell or PowerShell 7.\n")
                return
            exe = "powershell.exe"
            try:
                proc = subprocess.Popen([exe, "-NoLogo", "-NoProfile", "-Command", "-"], cwd=str(APP_DIR),
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                session["process"] = proc
                status.configure(text=f"SESSION ACTIVE · PID {proc.pid} · STANDARD USER", fg=ACCENT)
                append("DILARA PowerShell session started. Full-screen interactive terminal apps are not supported in this embedded console.\n")
                def reader():
                    try:
                        for line in proc.stdout:
                            session["queue"].put(line)
                    except (OSError, ValueError) as exc:
                        session["queue"].put(f"[reader] {exc}\n")
                    finally:
                        session["queue"].put(None)
                threading.Thread(target=reader, daemon=True).start()
                self._record_activity("terminal_launched", "D-TERMINAL")
            except OSError as exc:
                status.configure(text="LAUNCH FAILED", fg=WARN); append(f"Could not start PowerShell: {exc}\n")

        def poll_output():
            if not output.winfo_exists(): return
            session = self.terminal_sessions.get(session_key)
            if not session: return
            try:
                while True:
                    item = session["queue"].get_nowait()
                    if item is None:
                        proc = session.get("process")
                        if proc and proc.poll() is not None:
                            status.configure(text=f"SESSION EXITED · CODE {proc.returncode}", fg=WARN)
                        break
                    append(item)
            except queue.Empty: pass
            try: self.root.after(70, poll_output)
            except tk.TclError: pass

        def send_command(_event=None):
            text = command.get()
            if not text.strip(): return "break"
            session = self.terminal_sessions.get(session_key)
            proc = session.get("process") if session else None
            if not proc or proc.poll() is not None:
                start_session(); proc = session.get("process") if session else None
            if proc and proc.poll() is None and proc.stdin:
                try:
                    append(f"PS> {text}\n")
                    proc.stdin.write(text + "\n"); proc.stdin.flush()
                except (OSError, BrokenPipeError) as exc: append(f"Input failed: {exc}\n")
            command.delete(0, "end")
            return "break"

        tk.Button(toolbar, text="Start / Restart", command=start_session, bg=PANEL_2, fg=ACCENT, relief="flat", padx=9).pack(side="right", padx=(4, 0))
        tk.Button(toolbar, text="Stop session", command=lambda: self.close_terminal_session(win, terminate=True), bg=PANEL_2, fg=WARN, relief="flat", padx=9).pack(side="right")
        tk.Button(entry_row, text="Run", command=send_command, bg=ACCENT, fg="#071014", relief="flat", padx=12).pack(side="left", padx=(7, 0))
        command.bind("<Return>", send_command)
        command.focus_set()
        # Start a fresh standard-user process for an explicit workspace launch, but never on restore.
        if not getattr(win, "restoring", False):
            start_session()
        poll_output()

    def launch_powershell(self):
        # Kept as a compatibility entry point; the workspace now hosts the process itself.
        self.open_module("D-TERMINAL")

    def close_terminal_session(self, win, terminate=False):
        session = self.terminal_sessions.get(id(win))
        if not session:
            return
        proc = session.get("process")
        if proc and proc.poll() is None:
            try:
                if terminate: proc.terminate()
                elif proc.stdin: proc.stdin.write("exit\n"); proc.stdin.flush()
            except (OSError, BrokenPipeError):
                try: proc.terminate()
                except OSError: pass
        session["process"] = None if terminate else proc

    def _dispose_window(self, win):
        # Close a browser process hosted by this workspace before destroying its parent frame.
        if self.browser_owner is win and self.browser_adapter.is_running():
            try: self.browser_adapter.process.terminate()
            except (OSError, AttributeError): pass
            self.browser_owner = None
            self._embedded_browser_hwnd = None
            self._embedded_browser_host = None
        # Close sessions owned by this window (including terminals hosted in stack tabs).
        for session_key, owner in list(self._terminal_owner.items()):
            if owner is win:
                session = self.terminal_sessions.pop(session_key, None)
                self._terminal_owner.pop(session_key, None)
                if session:
                    proc = session.get("process")
                    if proc and proc.poll() is None:
                        try: proc.terminate()
                        except OSError: pass
        for proxy in getattr(win, "_stack_proxies", []):
            self.close_terminal_session(proxy, terminate=True)

    def _build_chaos_workspace(self, win):
        body=win.body
        tk.Label(body,text="BOUNDED NETWORK DIAGNOSTICS",bg=PANEL,fg=TEXT,font=("Segoe UI",10,"bold")).pack(anchor="w")
        tk.Label(body,text="This first adapter offers a low-rate TCP connection check only. Use it only against systems you own or are explicitly authorized to test. No packet flooding, scanning ranges, or traffic generation is implemented.",bg=PANEL,fg=MUTED,font=("Segoe UI",9),wraplength=490,justify="left").pack(anchor="w",pady=(6,12))
        form=tk.Frame(body,bg=PANEL); form.pack(fill="x")
        tk.Label(form,text="Hostname / IP",bg=PANEL,fg=MUTED).grid(row=0,column=0,sticky="w")
        host=tk.Entry(form,bg="#0a1119",fg=TEXT,insertbackground=TEXT,relief="flat",width=28); host.grid(row=0,column=1,sticky="ew",padx=8,pady=4)
        tk.Label(form,text="TCP port",bg=PANEL,fg=MUTED).grid(row=1,column=0,sticky="w")
        port=tk.Entry(form,bg="#0a1119",fg=TEXT,insertbackground=TEXT,relief="flat",width=10); port.insert(0,"443"); port.grid(row=1,column=1,sticky="w",padx=8,pady=4)
        status=tk.Label(body,text="Idle",bg=PANEL,fg=ACCENT,font=("Consolas",9)); status.pack(anchor="w",pady=8)
        cancel={"event":None}
        def check():
            import socket, threading
            h=host.get().strip()
            try: p=int(port.get().strip())
            except ValueError: messagebox.showwarning("CHAOS","Port must be an integer from 1 to 65535."); return
            if not h or not (1 <= p <= 65535): messagebox.showwarning("CHAOS","Enter a host and a TCP port from 1 to 65535."); return
            if not messagebox.askyesno("Confirm authorized check",f"Attempt one TCP connection to {h}:{p}? Continue only if authorized."): return
            cancel["flag"]=False; status.configure(text=f"Checking {h}:{p}…",fg=WARN); run_btn.configure(state="disabled")
            def worker():
                import time
                started=time.monotonic()
                try:
                    with socket.create_connection((h,p),timeout=3): result=f"TCP connection succeeded ({time.monotonic()-started:.2f}s)"
                except OSError as exc: result=f"Connection failed: {exc}"
                self.root.after(0,lambda: finish(result,h,p))
            def finish(result,h,p):
                status.configure(text=result,fg=ACCENT if result.startswith("TCP connection succeeded") else WARN); run_btn.configure(state="normal")
                self._record_activity("tcp_check_completed", "CHAOS")
            threading.Thread(target=worker,daemon=True).start()
        run_btn=tk.Button(body,text="Run one TCP check",command=check,bg=ACCENT,fg="#071014",relief="flat",padx=12,pady=7); run_btn.pack(anchor="w")

    def open_apps_users(self):
        top = tk.Toplevel(self.root); top.title("DILARA // Apps & Users"); top.geometry("760x620"); top.configure(bg=BG)
        tk.Label(top, text="APPS & USERS", bg=BG, fg=ACCENT, font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=(16, 3))
        tk.Label(top, text="DILARA can discover added apps from apps/<folder>/app.json or register them here. Registration never executes the app automatically.", bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=700, justify="left").pack(anchor="w", padx=18, pady=(0, 12))
        listbox = tk.Listbox(top, bg="#0a1119", fg=TEXT, selectbackground="#244a50", relief="flat", height=8)
        listbox.pack(fill="x", padx=18, pady=4)
        def refresh_apps():
            listbox.delete(0, "end")
            for a in self.app_registry.list_apps(): listbox.insert("end", f"{a.get('name')}  [{a.get('kind','python')}]  —  {a.get('description','')}")
        refresh_apps()
        form = tk.Frame(top, bg=BG); form.pack(fill="x", padx=18, pady=8)
        entries = {}
        for i, (key, label_text, width) in enumerate([("id", "App ID", 20), ("name", "Display name", 28), ("description", "Description", 36), ("entrypoint", "Script path, folder, or URL", 50)]):
            tk.Label(form, text=label_text, bg=BG, fg=MUTED, font=("Segoe UI", 8)).grid(row=i, column=0, sticky="w", pady=3)
            e = tk.Entry(form, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=width)
            e.grid(row=i, column=1, sticky="ew", padx=8, pady=3, ipady=4); entries[key] = e
        tk.Label(form, text="Type", bg=BG, fg=MUTED).grid(row=4, column=0, sticky="w", pady=3)
        kind = tk.StringVar(value="python")
        kind_box = ttk.Combobox(form, textvariable=kind, values=("python", "url", "folder"), state="readonly", width=15)
        kind_box.grid(row=4, column=1, sticky="w", padx=8, pady=3)
        browse_btn = tk.Button(form, text="Browse…", bg=PANEL_2, fg=TEXT, relief="flat", padx=10)
        browse_btn.grid(row=3, column=2, sticky="w", padx=(0, 4), pady=3)
        form.columnconfigure(1, weight=1)

        def browse_entrypoint():
            selected_kind = kind.get()
            if selected_kind == "python":
                chosen = filedialog.askopenfilename(parent=top, title="Select Python app entry point", filetypes=[("Python files", "*.py"), ("All files", "*.*")], initialdir=str(APP_DIR))
            elif selected_kind == "folder":
                chosen = filedialog.askdirectory(parent=top, title="Select application folder", initialdir=str(APP_DIR))
            else:
                messagebox.showinfo("Apps & Users", "For URL apps, enter an http:// or https:// address in the entry-point field.", parent=top)
                entries["entrypoint"].focus_set()
                return
            if chosen:
                entries["entrypoint"].delete(0, "end")
                entries["entrypoint"].insert(0, chosen)
                if not entries["id"].get().strip():
                    import re
                    auto_id = re.sub(r"[^a-zA-Z0-9_.-]+", "-", Path(chosen).stem if selected_kind == "python" else Path(chosen).name).strip("-.")
                    auto_id = (auto_id or "new-app")[:48]
                    if len(auto_id) < 2: auto_id = "app-" + auto_id
                    entries["id"].insert(0, auto_id)
                if not entries["name"].get().strip():
                    entries["name"].insert(0, Path(chosen).stem if selected_kind == "python" else Path(chosen).name)

        browse_btn.configure(command=browse_entrypoint)
        def update_browse_label(*_):
            browse_btn.configure(state=("normal" if kind.get() != "url" else "disabled"))
        kind.trace_add("write", update_browse_label)
        def add_app():
            try:
                self.app_registry.add_app(entries["id"].get().strip(), entries["name"].get().strip(), entries["description"].get().strip(), entries["entrypoint"].get().strip(), kind.get())
                refresh_apps(); messagebox.showinfo("Apps & Users", "App registered. It will appear in D-LLM's app list; no code was executed during registration.", parent=top)
            except (ValueError, OSError, json.JSONDecodeError) as exc: messagebox.showerror("Apps & Users", str(exc), parent=top)
        buttons = tk.Frame(top, bg=BG); buttons.pack(fill="x", padx=18, pady=4)
        tk.Button(buttons, text="Register app", command=add_app, bg=ACCENT, fg="#071014", relief="flat", padx=12, pady=6).pack(side="left")
        tk.Button(buttons, text="Open apps folder", command=lambda: self.open_path(self.app_registry.apps_dir), bg=PANEL_2, fg=TEXT, relief="flat", padx=12, pady=6).pack(side="left", padx=8)
        tk.Label(top, text="USER ACCOUNTS", bg=BG, fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(16, 5))
        users = UserStore(USER_STORE_FILE)
        user_list = tk.Listbox(top, bg="#0a1119", fg=TEXT, selectbackground="#244a50", relief="flat", height=4)
        user_list.pack(fill="x", padx=18)
        def refresh_users():
            user_list.delete(0, "end")
            for uname, info in users.users().items(): user_list.insert("end", f"{uname}  |  {info.get('role','user')}  |  {'enabled' if info.get('enabled', True) else 'disabled'}")
        refresh_users()
        userform = tk.Frame(top, bg=BG); userform.pack(fill="x", padx=18, pady=8)
        uname = tk.Entry(userform, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=18); uname.pack(side="left", ipady=5)
        password = tk.Entry(userform, show="•", bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=22); password.pack(side="left", padx=6, ipady=5)
        role = tk.StringVar(value="user"); ttk.Combobox(userform, textvariable=role, values=("user", "admin"), state="readonly", width=8).pack(side="left", padx=4)
        def add_user():
            if self.user.get("role") != "admin": messagebox.showwarning("Users", "Only an administrator can create users.", parent=top); return
            try:
                users.create_user(uname.get().strip(), password.get(), role.get()); refresh_users(); uname.delete(0, "end"); password.delete(0, "end")
                messagebox.showinfo("Users", "Account created. The password verifier is stored locally; the password itself is not saved.", parent=top)
            except (AuthError, OSError) as exc: messagebox.showerror("Users", str(exc), parent=top)
        tk.Button(userform, text="Create user", command=add_user, bg=ACCENT, fg="#071014", relief="flat", padx=10).pack(side="left", padx=5)
        if self.user.get("role") != "admin":
            tk.Label(top, text="User creation is administrator-only. App registration is available to the current user in this prototype.", bg=BG, fg=WARN, font=("Segoe UI", 8)).pack(anchor="w", padx=18, pady=4)

    def launch_registered_app(self, app):
        if not app.get("enabled", True): return
        kind = app.get("kind", "python"); entry = app.get("entrypoint", "")
        try:
            if kind == "url":
                import webbrowser; webbrowser.open(entry)
            elif kind == "folder":
                path = Path(entry)
                if not path.exists(): raise FileNotFoundError(path)
                self.open_path(path)
            elif kind == "python":
                path = Path(entry)
                if not path.is_absolute(): path = (APP_DIR / path).resolve()
                if not path.is_file(): raise FileNotFoundError(path)
                if not messagebox.askyesno("Launch added app", f"Launch registered app '{app.get('name')}'?\n\n{path}\n\nOnly register scripts you trust."): return
                subprocess.Popen([sys.executable, str(path)], cwd=str(path.parent))
            else: raise ValueError("Unsupported app type")
            self._record_activity("registered_app_launched", "APP_REGISTRY")
        except (OSError, ValueError) as exc: messagebox.showerror("App registry", str(exc))

    def sign_out(self):
        if not messagebox.askyesno("Sign out", f"Save and encrypt {self.user['username']}'s vault, then return to the login page?"): return
        if self.browser_adapter.is_running():
            messagebox.showwarning("Close browser first", "DILARA Browser is still running and uses this user's vault. Close the browser window, then sign out so its profile can be sealed consistently.")
            return
        try:
            self.vault.seal()
        except (VaultError, OSError) as exc:
            messagebox.showerror("Vault", f"The vault could not be sealed. Your session remains open so you can retry.\n\n{exc}")
            return
        self._record_activity("user_signed_out", "SYSTEM")
        for child in self.root.winfo_children(): child.destroy()
        AuthGate(self.root, self._enter_user)

    def _enter_user(self, user, password):
        vault = VaultManager(APP_DIR, user["username"], user.get("vault_id"))
        vault.unlock(password)
        for child in self.root.winfo_children(): child.destroy()
        DilaraApp(self.root, user, vault)

    def open_path(self, path):
        try:
            if sys.platform == "win32": os_start=["explorer.exe", str(path)]
            elif sys.platform == "darwin": os_start=["open", str(path)]
            else: os_start=["xdg-open", str(path)]
            subprocess.Popen(os_start)
        except OSError as exc: messagebox.showerror("DILARA", str(exc))

    def launch_kod8_side_app(self):
        ui_path = APP_DIR / "KOD8_ENC" / "kod8_ui.py"
        if not ui_path.is_file():
            messagebox.showerror("KOD8", f"KOD8 side app not found:\n{ui_path}")
            return
        try:
            subprocess.Popen([sys.executable, str(ui_path)], cwd=str(ui_path.parent))
            self._record_activity("side_app_launched", "KOD8")
        except OSError as exc:
            messagebox.showerror("KOD8", f"Could not launch KOD8 side app:\n{exc}")

    def refresh_taskbar(self):
        if not hasattr(self, "task_buttons"): return
        for child in self.task_buttons.winfo_children(): child.destroy()
        for key, win in self.windows.items():
            color = ACCENT if win is self.active and not win.minimized else TEXT
            btn = tk.Button(self.task_buttons, text=key, command=win.restore, bg="#0c131c", fg=color,
                            activebackground=PANEL_2, activeforeground=ACCENT, relief="flat", bd=0,
                            padx=10, font=("Consolas", 8), cursor="hand2")
            btn.pack(side="left", fill="y", padx=1)

    def _load_state(self):
        CONFIG_DIR.mkdir(exist_ok=True)
        try: self.saved_state = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): self.saved_state = {}
        if not isinstance(self.saved_state, dict): self.saved_state = {}

    def _write_state_silently(self):
        state = {"version": 2, "windows": {k: [w.x, w.y, w.w, w.h] for k, w in self.windows.items() if not w.minimized},
                 "wallpaper": {"color": self.wallpaper_color, "path": self.wallpaper_path},
                 "stack_keys": getattr(self.windows.get("STACK"), "stack_keys", [])}
        self.saved_state = state
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError as exc:
            print(f"[DILARA state] {exc}", file=sys.stderr)

    def _restore_layout(self):
        # Only restore window geometry; never auto-launch operations or privileged sessions.
        for key, geo in self.saved_state.get("windows", {}).items():
            if key not in {m[0] for m in MODULES}: continue
            try:
                if key == "STACK":
                    keys = [k for k in self.saved_state.get("stack_keys", []) if k in {m[0] for m in MODULES} and k not in {"STACK", "D-LLM", "D-ARCADE"}]
                    if not keys: continue
                    self._create_stacked_window(keys, restoring=True)
                else:
                    self.open_module(key, restoring=True)
                win = self.windows[key]
                win.x, win.y = max(0, int(geo[0])), max(0, int(geo[1]))
                win.w, win.h = max(340, int(geo[2])), max(220, int(geo[3]))
                win.frame.place_configure(x=win.x, y=win.y, width=win.w, height=win.h)
            except (ValueError, TypeError, IndexError):
                pass

    def save_state(self):
        state = {"version": 2, "windows": {k: [w.x, w.y, w.w, w.h] for k, w in self.windows.items() if not w.minimized},
                 "wallpaper": {"color": self.wallpaper_color, "path": self.wallpaper_path},
                 "stack_keys": getattr(self.windows.get("STACK"), "stack_keys", [])}
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
            messagebox.showinfo("DILARA", "Desktop layout saved. No module operations or privileged sessions are resumed automatically.")
        except OSError as exc:
            messagebox.showerror("DILARA", f"Could not save layout:\n{exc}")

    def about(self):
        messagebox.showinfo("DILARA // Status", "DILARA desktop environment\n\n• Local multi-user sign-in with PBKDF2 password verifiers\n• Per-user desktop layouts and resource registries\n• Discoverable app registry for future modules\n• Custom in-progress D-LLM core and no-network utility fallback\n• No boot animation and no automatic elevation\n\nPrototype limitation: local accounts are application-level, not Windows security principals.")

    def _tick_clock(self):
        import datetime
        self.clock.configure(text=datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def shutdown(self):
        if not messagebox.askyesno("DILARA", "Save and encrypt the user vault, then close DILARA?"):
            return
        if self.browser_adapter.is_running():
            try: self.browser_adapter.process.terminate()
            except (OSError, AttributeError): pass
        try:
            self.vault.seal()
        except (VaultError, OSError) as exc:
            messagebox.showerror("Vault", f"The vault could not be sealed. DILARA will remain open so you can retry.\n\n{exc}")
            return
        self._record_activity("session_ended", "SYSTEM")
        self._stop_wallpaper_animation()
        for session in list(self.terminal_sessions.values()):
            proc = session.get("process")
            if proc and proc.poll() is None:
                try: proc.terminate()
                except OSError: pass
        self.root.destroy()

class AuthGate:
    def __init__(self, root, on_success):
        self.root, self.on_success = root, on_success
        self.store = UserStore(USER_STORE_FILE)
        self.root.title("DILARA // Sign in")
        self.root.geometry("560x500"); self.root.minsize(480, 440); self.root.configure(bg=BG)
        self._build_setup() if not self.store.has_users() else self._build_login()

    def _clear(self):
        for child in self.root.winfo_children(): child.destroy()

    def _base(self, subtitle):
        self._clear()
        outer = tk.Frame(self.root, bg=BG, padx=42, pady=32); outer.pack(fill="both", expand=True)
        tk.Label(outer, text="DILARA", bg=BG, fg=TEXT, font=("Segoe UI", 28, "bold")).pack(anchor="w")
        tk.Label(outer, text="LOCAL DESKTOP ENVIRONMENT  /  5.0", bg=BG, fg=ACCENT, font=("Consolas", 9)).pack(anchor="w", pady=(0, 24))
        tk.Label(outer, text=subtitle, bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 12))
        return outer

    def _field(self, parent, label, secret=False):
        tk.Label(parent, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 3))
        field = tk.Entry(parent, show="•" if secret else "", bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 11))
        field.pack(fill="x", ipady=8); return field

    def _build_setup(self):
        outer = self._base("FIRST RUN  /  CREATE THE LOCAL ADMINISTRATOR")
        tk.Label(outer, text="No accounts exist yet. Create the first administrator account to initialize DILARA.", bg=BG, fg=TEXT, font=("Segoe UI", 9), wraplength=440, justify="left").pack(anchor="w")
        self.username = self._field(outer, "Administrator username")
        self.password = self._field(outer, "Password (minimum 10 characters)", True)
        self.confirm = self._field(outer, "Confirm password", True)
        self.error = tk.Label(outer, text="", bg=BG, fg="#ff7585", font=("Segoe UI", 9)); self.error.pack(anchor="w", pady=6)
        tk.Button(outer, text="Create administrator & enter DILARA", command=self._create_admin, bg=ACCENT, fg="#071014", relief="flat", padx=14, pady=10, font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(6, 0))

    def _create_admin(self):
        if self.password.get() != self.confirm.get(): self.error.configure(text="Passwords do not match."); return
        try:
            user = self.store.create_user(self.username.get().strip(), self.password.get(), "admin")
            self.on_success(user, self.password.get())
        except (AuthError, VaultError, OSError) as exc: self.error.configure(text=str(exc))

    def _build_login(self):
        outer = self._base("SIGN IN  /  SELECT YOUR LOCAL USER ACCOUNT")
        self.username = self._field(outer, "Username")
        self.password = self._field(outer, "Password", True)
        self.error = tk.Label(outer, text="", bg=BG, fg="#ff7585", font=("Segoe UI", 9)); self.error.pack(anchor="w", pady=8)
        tk.Button(outer, text="Sign in", command=self._login, bg=ACCENT, fg="#071014", relief="flat", padx=14, pady=10, font=("Segoe UI", 10, "bold")).pack(fill="x")
        tk.Label(outer, text="Local application accounts · each user has separate layout and resource data", bg=BG, fg=MUTED, font=("Segoe UI", 8), wraplength=430).pack(anchor="w", pady=(16, 0))
        self.username.bind("<Return>", lambda _e: self.password.focus_set()); self.password.bind("<Return>", lambda _e: self._login()); self.username.focus_set()

    def _login(self):
        try: user = self.store.authenticate(self.username.get().strip(), self.password.get())
        except AuthError as exc: self.error.configure(text=str(exc)); return
        if not user: self.error.configure(text="Invalid username or password, or account disabled."); return
        try:
            self.on_success(user, self.password.get())
        except (VaultError, OSError) as exc:
            self.error.configure(text=str(exc))

def launch_application():
    root = tk.Tk()
    def enter(user, password):
        vault = VaultManager(APP_DIR, user["username"], user.get("vault_id"))
        vault.unlock(password)
        for child in root.winfo_children(): child.destroy()
        # The password is used to derive a session key, then is not retained by
        # the desktop object or written to configuration/container files.
        DilaraApp(root, user, vault)
    AuthGate(root, enter)
    root.mainloop()

def main(): launch_application()

if __name__ == "__main__":
    main()
