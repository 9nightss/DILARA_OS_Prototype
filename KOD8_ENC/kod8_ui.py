#!/usr/bin/env python3
# =============================================================================
# KOD 8 - desktop demo UI
# Needs kod8_engine2.py (the corrected engine) next to this file.
#
#   Ctrl+Enter          encrypt
#   Ctrl+Shift+Enter    decrypt
# =============================================================================

import base64
import os
import queue
import re
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, ttk

# Crisp text on high-DPI Windows displays (must run before the Tk root exists).
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kod8_engine import run_kod8_pipeline, CIPHER_LISTS  # noqa: E402
from kod8_engine import _detect_turkish, _detect_numeric  # noqa: E402


# ═════════════════════════════════════════════════════════════════════════════
# PALETTE - light instrument chrome, dark readout windows, one signal red
# ═════════════════════════════════════════════════════════════════════════════
class C:
    HEADER      = "#18202A"
    HEADER_CHIP = "#222D3A"
    HEADER_LINE = "#364353"
    HEADER_FG   = "#EEF2F6"
    HEADER_DIM  = "#9AA8B6"

    BG            = "#E8ECEF"
    CARD          = "#FFFFFF"
    BORDER        = "#D3D9DF"
    BORDER_STRONG = "#B3BDC7"

    INK       = "#18202A"
    INK_DIM   = "#55616D"
    INK_FAINT = "#7E8A96"

    RED      = "#D92B3A"
    RED_H    = "#C32532"
    RED_P    = "#A91E2A"
    RED_HALO = "#F2B5BB"
    GREEN    = "#1E9E75"

    WELL      = "#1A232E"
    WELL_FG   = "#D7E0E9"
    WELL_DIM  = "#7D8FA2"
    WELL_MINT = "#9FE3C4"
    WELL_SEL  = "#35516B"
    WAIT_BG   = "#EDF0F3"


STRATEGY_LABEL = {
    "CL1": "ASCII plain text",
    "CL2": "Numeric strings",
    "CL3": "Document files",
    "CL4": "Image data",
    "CL5": "Video data",
    "CL6": "Fallback engine 1",
    "CL7": "Fallback engine 2",
    "CL8": "Turkish special chars",
}

STEP_META = {
    "op_mlkem_encap":           "ML-KEM Post-Quantum Lattice (Node 8)",
    "op_blake3_seed_prep":      "BLAKE3 Dynamic Seed Prep (Node 8)",
    "op_turkish_normalize":     "Turkish Character Set Normalize (Node 8)",
    "op_rocca_s_stream":        "Rocca-S SIMD Stream Transformation (Node 6)",
    "op_galois_field_mult":     "GF(2^8) Galois Field Modulation (Node 6)",
    "op_dynamic_split":         "Inter-Block Positional Split (Node 2)",
    "op_base36_pack":           "Base36 Integer Transposition (Node 2)",
    "op_glevian_block":         "Glevian Block Matrix Mutation (Node 4)",
    "op_vigornian_sub":         "Vigornian State-Mutating Sub (Node 7)",
    "op_aegis256x":             "AEGIS-256X Extended Permutation (Node 9)",
    "op_prime_affine_transform": "Prime Modulo (p=257) Affine Shift (Node 9)",
    "op_ascon128_sponge":       "Ascon-128 Lightweight Sponge Diffusion (Node 3)",
    "op_full_reverse":          "Terminal Script Reversal (Node 1)",
}
_NODE_RE = re.compile(r"^(.*?)\s*\(Node (\d+)\)\s*$")


def step_label(fn_name):
    raw = STEP_META.get(fn_name, fn_name)
    m = _NODE_RE.match(raw)
    return (m.group(1), f"Node {m.group(2)}") if m else (raw, "")


MAX_VIEW_CHARS = 200_000   # the output pane never renders more than this


# ═════════════════════════════════════════════════════════════════════════════
# .kod8 container header
#   # KOD8  cipher_id: CL4  bin: 1  ext: .png
# ═════════════════════════════════════════════════════════════════════════════
_HDR_RE = re.compile(
    r"^#\s*KOD8\s+cipher_id:\s*(CL\d+)(?:\s+bin:\s*([01]))?(?:\s+ext:\s*(\S+))?\s*$")


def make_header(cid, is_bin=False, ext=""):
    h = f"# KOD8  cipher_id: {cid}  bin: {int(bool(is_bin))}"
    if ext and not any(c.isspace() for c in ext):
        h += f"  ext: {ext}"
    return h


def parse_kod8(raw):
    """Returns (cipher_id or None, is_bin, ext, ciphertext_body)."""
    lines = raw.strip().splitlines()
    cid, is_bin, ext = None, False, ""
    if lines:
        m = _HDR_RE.match(lines[0].strip())
        if m:
            cid, is_bin, ext = m.group(1), m.group(2) == "1", m.group(3) or ""
            lines = lines[1:]
    if cid not in CIPHER_LISTS:
        cid = None
    return cid, is_bin, ext, "\n".join(lines).strip()


def auto_detect(sample_or_path, is_file=False):
    if is_file:
        ext = sample_or_path.lower().split(".")[-1]
        if ext in ("pdf", "docx", "doc", "txt", "xlsx", "pptx", "odt"):
            return "CL3"
        if ext in ("png", "jpg", "jpeg", "bmp", "webp", "gif", "svg"):
            return "CL4"
        if ext in ("mp4", "mkv", "avi", "mov", "webm", "flv"):
            return "CL5"
        return "CL6"
    if _detect_turkish(sample_or_path):
        return "CL8"
    if _detect_numeric(sample_or_path):
        return "CL2"
    return "CL1"


def elide(font, text, width):
    if width <= 20 or font.measure(text) <= width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.measure(text[:mid] + "…") <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + "…"


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


class Cancelled(Exception):
    pass


# ═════════════════════════════════════════════════════════════════════════════
# WIDGETS
# ═════════════════════════════════════════════════════════════════════════════
def rounded(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class RButton(tk.Canvas):
    STYLES = {
        "primary":   dict(bg=C.RED,  hover=C.RED_H,   press=C.RED_P,   fg="#FFFFFF", line=None),
        "secondary": dict(bg=C.CARD, hover="#F1F4F6", press="#E3E8EC", fg=C.INK,     line=C.BORDER_STRONG),
        "ghost":     dict(bg=None,   hover="#E9EDF1", press="#DCE2E8", fg=C.INK_DIM, line=None),
    }

    def __init__(self, master, app, text, command, kind="secondary",
                 font=None, parent_bg=C.CARD, padx=18, pady=8, min_w=0):
        self.app, self._text, self._cmd = app, text, command
        self._style, self._font = self.STYLES[kind], font
        px = app.px
        w = max(font.measure(text) + 2 * px(padx), px(min_w))
        h = font.metrics("linespace") + 2 * px(pady)
        super().__init__(master, width=w, height=h, bg=parent_bg,
                         highlightthickness=0, bd=0, takefocus=1, cursor="hand2")
        self._bw, self._bh = w, h
        self._hover = self._down = self._focus = False
        self._enabled = True
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, down=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(down=True))
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<FocusIn>", lambda e: self._set(focus=True))
        self.bind("<FocusOut>", lambda e: self._set(focus=False))
        self.bind("<space>", lambda e: self._fire())
        self.bind("<Return>", lambda e: self._fire())
        self._draw()

    def _set(self, **kw):
        for k, v in kw.items():
            setattr(self, "_" + k, v)
        self._draw()

    def _release(self, _):
        fire = self._down and self._hover
        self._set(down=False)
        if fire:
            self._fire()

    def _fire(self):
        if self._enabled and self._cmd:
            self._cmd()

    def set_enabled(self, enabled):
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def _draw(self):
        self.delete("all")
        st, r = self._style, self.app.px(7)
        if not self._enabled:
            fill, fg, line = "#DDE2E7", "#97A2AD", None
        else:
            fill = st["press"] if self._down else st["hover"] if self._hover else st["bg"]
            fg, line = st["fg"], st["line"]
        if fill:
            rounded(self, 1, 1, self._bw - 1, self._bh - 1, r,
                    fill=fill, outline=line or fill, width=1)
        self.create_text(self._bw // 2, self._bh // 2, text=self._text,
                         font=self._font, fill=fg)
        if self._focus and self._enabled:
            rounded(self, 3, 3, self._bw - 3, self._bh - 3, r,
                    fill="", outline=C.INK if st["bg"] != C.RED else "#FFFFFF", width=1)


class Chip(tk.Canvas):
    """Small rounded status chip with an optional coloured dot."""

    def __init__(self, master, app, font, text="", dot=None):
        self.app, self._font, self._text, self._dot = app, font, text, dot
        super().__init__(master, bg=C.HEADER, highlightthickness=0, bd=0)
        self._draw()

    def set(self, text, dot=None):
        self._text, self._dot = text, dot
        self._draw()

    def _draw(self):
        px = self.app.px
        pad, dot_w = px(12), (px(16) if self._dot else 0)
        w = pad * 2 + dot_w + self._font.measure(self._text)
        h = self._font.metrics("linespace") + px(12)
        self.configure(width=w, height=h)
        self.delete("all")
        rounded(self, 1, 1, w - 1, h - 1, h // 2 - 1,
                fill=C.HEADER_CHIP, outline=C.HEADER_LINE)
        x = pad
        if self._dot:
            r = px(4)
            self.create_oval(x, h // 2 - r, x + 2 * r, h // 2 + r,
                             fill=self._dot, outline="")
            x += dot_w
        self.create_text(x, h // 2, text=self._text, font=self._font,
                         fill=C.HEADER_FG, anchor="w")


class StageRow(tk.Frame):
    """One pipeline stage: rail node, stage name, and a readout of its output."""

    def __init__(self, master, app, index, total):
        super().__init__(master, bg=C.CARD)
        self.app, self.index, self.total = app, index, total
        self.state, self._full = "wait", ""
        px = app.px

        self.node = tk.Canvas(self, width=px(40), height=1, bg=C.CARD, highlightthickness=0)
        self.node.pack(side="left", fill="y")

        body = tk.Frame(self, bg=C.CARD)
        body.pack(side="left", fill="both", expand=True,
                  padx=(0, px(18)), pady=(px(7), px(7)))
        top = tk.Frame(body, bg=C.CARD)
        top.pack(fill="x")
        self.title = tk.Label(top, text="", font=app.f_ui_b, fg=C.INK_DIM,
                              bg=C.CARD, anchor="w")
        self.title.pack(side="left")
        self.meta = tk.Label(top, text="", font=app.f_small, fg=C.INK_FAINT,
                             bg=C.CARD, anchor="e")
        self.meta.pack(side="right")

        self.well = well = tk.Frame(body, bg=C.WAIT_BG)
        well.pack(fill="x", pady=(px(4), 0))
        self.read = tk.Label(well, text="", font=app.f_mono_s, fg=C.INK_FAINT,
                             bg=C.WAIT_BG, anchor="w", width=1)
        self.read.pack(side="left", fill="x", expand=True,
                       padx=(px(10), px(8)), pady=px(5))
        self.count = tk.Label(well, text="", font=app.f_small, fg=C.WELL_DIM,
                              bg=C.WAIT_BG, anchor="e")
        self.count.pack(side="right", padx=(0, px(10)))

        self.node.bind("<Configure>", lambda e: self._draw())
        self.read.bind("<Configure>", lambda e: self._fit())

    def set_name(self, fn_name):
        title, node = step_label(fn_name)
        self.title.configure(text=title)
        self.meta.configure(text=node)

    def _paint(self, bg, fg):
        for w in (self.well, self.read, self.count):
            w.configure(bg=bg)
        self.read.configure(fg=fg)

    def reset(self):
        self.state, self._full = "wait", ""
        self._paint(C.WAIT_BG, C.INK_FAINT)
        self.read.configure(text="Waiting")
        self.count.configure(text="")
        self.title.configure(fg=C.INK_DIM)
        self._draw()

    def set_state(self, state, value=None):
        self.state = state
        self.title.configure(fg=C.INK_DIM if state == "wait" else C.INK)
        if state == "active":
            self._full = ""
            self.read.configure(text="Working…", fg=C.WELL_DIM)
            self.count.configure(text="")
        elif state == "done":
            self._full = (value or "")[:400].replace("\r", "␍").replace("\n", "↵")
            self._paint(C.WELL, C.WELL_FG)
            self.count.configure(text=f"{len(value or ''):,} chars", fg=C.WELL_DIM)
            self._fit()
        self._draw()

    def _fit(self):
        if self._full:
            w = self.read.winfo_width() - 2
            self.read.configure(text=elide(self.app.f_mono_s, self._full, w))

    def _draw(self):
        c, px = self.node, self.app.px
        c.delete("all")
        h = c.winfo_height()
        if h < 4:
            return
        cx = px(20)
        cy = px(7) + self.title.winfo_reqheight() // 2
        lit_above = self.state in ("done", "active")
        lit_below = self.state == "done"
        if self.index > 0:
            c.create_line(cx, 0, cx, cy, width=px(2),
                          fill=C.GREEN if lit_above else C.BORDER)
        if self.index < self.total - 1:
            c.create_line(cx, cy, cx, h, width=px(2),
                          fill=C.GREEN if lit_below else C.BORDER)
        r = px(7)
        if self.state == "wait":
            c.create_oval(cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1,
                          fill=C.CARD, outline=C.BORDER_STRONG, width=px(2))
        elif self.state == "active":
            h_r = px(11)
            c.create_oval(cx - h_r, cy - h_r, cx + h_r, cy + h_r,
                          fill="", outline=C.RED_HALO, width=px(2))
            c.create_oval(cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1,
                          fill=C.RED, outline=C.RED)
        else:
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=C.GREEN, outline=C.GREEN)
            k = px(3)
            c.create_line(cx - k, cy, cx - 1, cy + k - 1, cx + k + 1, cy - k + 1,
                          fill="#FFFFFF", width=px(2), capstyle="round", joinstyle="round")


# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION
# ═════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("KOD8  Multi-layer cipher engine")
        self.configure(bg=C.BG)
        self.S = max(1.0, self.winfo_fpixels("1i") / 96.0)
        self._make_fonts()
        self._make_styles()

        # file / input state
        self._file_path = None
        self._file_bytes = None
        self._file_is_bin = False
        self._file_text_exact = None     # file text with its original newlines
        self._loaded_display = None      # what we put in the input box for it
        # run state
        self._busy = False
        self._enc = None                 # last encrypt job (for one-click round trip)
        self._out = None                 # what the output pane holds
        self._rail_has_run = False
        self._q = queue.Queue()
        self._preview_job = None

        self._build()

        w, h = self.px(1280), self.px(800)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(w, sw - 40), min(h, sh - 80)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
        self.minsize(self.px(1040), self.px(700))

        self.bind("<Control-Return>", lambda e: self._start("encrypt"))
        self.bind("<Control-Shift-Return>", lambda e: self._start("decrypt"))
        self._input_changed()

    # ── metrics / fonts / styles ─────────────────────────────────────────
    def px(self, n):
        return int(round(n * self.S))

    def _make_fonts(self):
        have = set(tkfont.families())
        base = tkfont.nametofont("TkDefaultFont").actual("family")

        def pick(*names):
            return next((n for n in names if n in have), base)

        ui = pick("Segoe UI Variable Text", "Segoe UI", "Inter", "SF Pro Text",
                  "Helvetica Neue", "Arial")
        mono = pick("Cascadia Mono", "Cascadia Code", "Consolas", "JetBrains Mono",
                    "SF Mono", "DejaVu Sans Mono", "Courier New")
        self.f_mark = tkfont.Font(family=ui, size=17, weight="bold")
        self.f_sub = tkfont.Font(family=ui, size=10)
        self.f_ui = tkfont.Font(family=ui, size=10)
        self.f_ui_b = tkfont.Font(family=ui, size=10, weight="bold")
        self.f_card = tkfont.Font(family=ui, size=11, weight="bold")
        self.f_btn = tkfont.Font(family=ui, size=11, weight="bold")
        self.f_small = tkfont.Font(family=ui, size=9)
        self.f_mono = tkfont.Font(family=mono, size=11)
        self.f_mono_s = tkfont.Font(family=mono, size=10)

    def _make_styles(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        layout = [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})]
        for name, trough, thumb in (("Light", C.CARD, "#C3CBD3"),
                                    ("Dark", C.WELL, "#44566A")):
            s = f"{name}.Vertical.TScrollbar"
            st.layout(s, layout)
            st.configure(s, troughcolor=trough, background=thumb, bordercolor=trough,
                         lightcolor=thumb, darkcolor=thumb, gripcount=0,
                         width=self.px(9))
            st.map(s, background=[("active", C.INK_FAINT if name == "Light" else "#5C7088")])

    # ── layout ───────────────────────────────────────────────────────────
    def _build(self):
        px = self.px
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # header
        head = tk.Frame(self, bg=C.HEADER)
        head.grid(row=0, column=0, sticky="ew")
        inner = tk.Frame(head, bg=C.HEADER)
        inner.pack(fill="x", padx=px(24), pady=px(14))
        mark = tk.Canvas(inner, width=px(14), height=px(14), bg=C.HEADER,
                         highlightthickness=0)
        mark.create_rectangle(0, 0, px(14), px(14), fill=C.RED, outline="")
        mark.pack(side="left", padx=(0, px(12)))
        tk.Label(inner, text="KOD8", font=self.f_mark, fg=C.HEADER_FG,
                 bg=C.HEADER).pack(side="left")
        tk.Label(inner, text="Multi-layer cipher engine", font=self.f_sub,
                 fg=C.HEADER_DIM, bg=C.HEADER).pack(side="left", padx=(px(16), 0), pady=(px(3), 0))
        self.chip_key = Chip(inner, self, self.f_small, "8-digit key loaded", C.GREEN)
        self.chip_key.pack(side="right")
        self.chip_strategy = Chip(inner, self, self.f_small, "Strategy: auto-detect", C.INK_FAINT)
        self.chip_strategy.pack(side="right", padx=(0, px(10)))

        # main area
        main = tk.Frame(self, bg=C.BG)
        main.grid(row=1, column=0, sticky="nsew", padx=px(24), pady=(px(20), px(14)))
        main.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=5, uniform="cols")
        main.columnconfigure(1, weight=6, uniform="cols")

        left = tk.Frame(main, bg=C.BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, px(10)))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1, uniform="io")
        left.rowconfigure(2, weight=1, uniform="io")

        right = tk.Frame(main, bg=C.BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(px(10), 0))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self._build_input(left)
        self._build_actions(left)
        self._build_output(left)
        self._build_pipeline(right)

        # status bar
        bar = tk.Frame(self, bg=C.CARD, highlightbackground=C.BORDER, highlightcolor=C.BORDER,
                        highlightthickness=1)
        bar.grid(row=2, column=0, sticky="ew")
        row = tk.Frame(bar, bg=C.CARD)
        row.pack(fill="x", padx=px(24), pady=px(9))
        self.dot = tk.Canvas(row, width=px(12), height=px(12), bg=C.CARD, highlightthickness=0)
        self.dot.pack(side="left", padx=(0, px(10)))
        self.status = tk.Label(row, text="", font=self.f_ui, fg=C.INK, bg=C.CARD,
                               anchor="w", justify="left")
        self.status.pack(side="left", fill="x", expand=True)
        self.status.bind("<Configure>",
                         lambda e: self.status.configure(wraplength=max(200, e.width - 4)))
        self._set_status("ready", "Ready. Type or paste text, or open a file.")

    def _card(self, parent, title):
        px = self.px
        card = tk.Frame(parent, bg=C.CARD, highlightbackground=C.BORDER, highlightcolor=C.BORDER,
                        highlightthickness=1)
        head = tk.Frame(card, bg=C.CARD)
        head.pack(fill="x", padx=px(16), pady=(px(10), px(6)))
        tk.Label(head, text=title, font=self.f_card, fg=C.INK, bg=C.CARD).pack(side="left")
        tools = tk.Frame(head, bg=C.CARD)
        tools.pack(side="right")
        meta = tk.Label(head, text="", font=self.f_small, fg=C.INK_FAINT, bg=C.CARD)
        meta.pack(side="right", padx=(0, px(10)))
        tk.Frame(card, bg=C.BORDER, height=1).pack(fill="x")
        return card, tools, meta

    def _build_input(self, parent):
        px = self.px
        card, tools, self.in_meta = self._card(parent, "Input")
        card.grid(row=0, column=0, sticky="nsew")
        RButton(tools, self, "Open file…", self._open_file, "ghost", self.f_ui_b,
                padx=10, pady=4).pack(side="left")
        RButton(tools, self, "Clear", self._clear, "ghost", self.f_ui_b,
                padx=10, pady=4).pack(side="left")

        body = tk.Frame(card, bg=C.CARD)
        body.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(body, orient="vertical", style="Light.Vertical.TScrollbar")
        sb.pack(side="right", fill="y")
        self.input = tk.Text(body, font=self.f_mono, bg=C.CARD, fg=C.INK, relief="flat",
                             bd=0, wrap="word", padx=px(16), pady=px(12), undo=True,
                             height=1, insertbackground=C.RED, highlightthickness=0,
                             selectbackground="#F7CBD0", selectforeground=C.INK,
                             yscrollcommand=sb.set)
        self.input.pack(side="left", fill="both", expand=True)
        sb.configure(command=self.input.yview)
        self.ph = tk.Label(self.input, justify="left", font=self.f_ui, fg=C.INK_FAINT,
                           bg=C.CARD, anchor="nw", cursor="xterm",
                           text="Type or paste text to encrypt.\n"
                                "Paste ciphertext, or open a .kod8 file, to decrypt.")
        self.ph.place(x=px(16), y=px(12))
        self.ph.bind("<Button-1>", lambda e: self.input.focus_set())
        self.input.bind("<<Modified>>", self._on_modified)
        self.input.bind("<Control-Return>",
                        lambda e: (self._start("encrypt"), "break")[1])
        self.input.bind("<Control-Shift-Return>",
                        lambda e: (self._start("decrypt"), "break")[1])

    def _build_actions(self, parent):
        px = self.px
        row = tk.Frame(parent, bg=C.BG)
        row.grid(row=1, column=0, sticky="ew", pady=px(12))
        self.btn_enc = RButton(row, self, "Encrypt", lambda: self._start("encrypt"),
                               "primary", self.f_btn, parent_bg=C.BG, padx=34, pady=11, min_w=150)
        self.btn_enc.pack(side="left")
        self.btn_dec = RButton(row, self, "Decrypt", lambda: self._start("decrypt"),
                               "secondary", self.f_btn, parent_bg=C.BG, padx=34, pady=11, min_w=150)
        self.btn_dec.pack(side="left", padx=(px(12), 0))

    def _build_output(self, parent):
        px = self.px
        card, tools, self.out_meta = self._card(parent, "Output")
        card.grid(row=2, column=0, sticky="nsew")
        self.btn_copy = RButton(tools, self, "Copy", self._copy, "ghost", self.f_ui_b,
                                padx=10, pady=4)
        self.btn_copy.pack(side="left")
        self.btn_save = RButton(tools, self, "Save…", self._save, "ghost", self.f_ui_b,
                                padx=10, pady=4)
        self.btn_save.pack(side="left")
        self.btn_copy.set_enabled(False)
        self.btn_save.set_enabled(False)

        body = tk.Frame(card, bg=C.WELL)
        body.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(body, orient="vertical", style="Dark.Vertical.TScrollbar")
        sb.pack(side="right", fill="y")
        self.output = tk.Text(body, font=self.f_mono, bg=C.WELL, fg=C.WELL_FG, relief="flat",
                              bd=0, wrap="char", padx=px(16), pady=px(12), height=1,
                              highlightthickness=0, insertbackground=C.WELL_FG,
                              selectbackground=C.WELL_SEL, selectforeground="#FFFFFF",
                              yscrollcommand=sb.set, state="disabled", cursor="arrow")
        self.output.pack(side="left", fill="both", expand=True)
        sb.configure(command=self.output.yview)
        self.output.bind("<Button-1>", lambda e: self.output.focus_set())
        self._set_output_text("The result appears here.", dim=True)

    def _build_pipeline(self, parent):
        px = self.px
        card = tk.Frame(parent, bg=C.CARD, highlightbackground=C.BORDER, highlightcolor=C.BORDER,
                        highlightthickness=1)
        card.grid(row=0, column=0, sticky="nsew")
        head = tk.Frame(card, bg=C.CARD)
        head.pack(fill="x", padx=px(16), pady=(px(10), px(6)))
        tk.Label(head, text="Pipeline", font=self.f_card, fg=C.INK, bg=C.CARD).pack(side="left")
        self.prog_label = tk.Label(head, text="0 of 8", font=self.f_small,
                                   fg=C.INK_FAINT, bg=C.CARD)
        self.prog_label.pack(side="right")
        self.prog = tk.Canvas(card, height=px(3), bg=C.BORDER, highlightthickness=0)
        self.prog.pack(fill="x")
        self._prog_frac, self._prog_color = 0.0, C.RED
        self.prog.bind("<Configure>", lambda e: self._draw_progress())

        rows = tk.Frame(card, bg=C.CARD)
        rows.pack(fill="both", expand=True, pady=(px(6), px(6)))
        rows.columnconfigure(0, weight=1)
        self.rows = []
        n = 8
        for i in range(n):
            rows.rowconfigure(i, weight=1, uniform="stage")
            r = StageRow(rows, self, i, n)
            r.grid(row=i, column=0, sticky="nsew")
            self.rows.append(r)
        self._reset_rail(list(CIPHER_LISTS["CL1"]["steps"]))

    # ── small helpers ────────────────────────────────────────────────────
    def _draw_progress(self):
        self.prog.delete("all")
        w, h = self.prog.winfo_width(), self.prog.winfo_height()
        if self._prog_frac > 0:
            self.prog.create_rectangle(0, 0, int(w * self._prog_frac), h,
                                       fill=self._prog_color, outline="")

    def _set_progress(self, done, total=8, color=C.RED):
        self._prog_frac, self._prog_color = done / total, color
        self.prog_label.configure(text=f"{done} of {total}")
        self._draw_progress()

    def _set_status(self, kind, msg):
        color = {"ready": C.INK_FAINT, "busy": C.RED, "ok": C.GREEN, "error": C.RED}[kind]
        px = self.px
        self.dot.delete("all")
        self.dot.create_oval(px(1), px(1), px(11), px(11), fill=color, outline="")
        self.status.configure(text=msg, fg=C.RED if kind == "error" else C.INK)

    def _reset_rail(self, steps):
        for row, (fn, _) in zip(self.rows, steps):
            row.set_name(fn.__name__)
            row.reset()
        self._set_progress(0)
        self._rail_has_run = False

    def _set_buttons(self, busy):
        self.btn_enc.set_enabled(not busy)
        self.btn_dec.set_enabled(not busy)

    def _set_strategy_chip(self, cid):
        if cid:
            self.chip_strategy.set(f"{cid}  {STRATEGY_LABEL.get(cid, '')}", C.RED)
        else:
            self.chip_strategy.set("Strategy: auto-detect", C.INK_FAINT)

    # ── input area ───────────────────────────────────────────────────────
    def _set_input(self, text, dim=False, locked=False):
        self.input.configure(state="normal")
        self.input.delete("1.0", "end")
        self.input.insert("1.0", text)
        self.input.configure(fg=C.INK_DIM if dim else C.INK,
                             state="disabled" if locked else "normal")

    def _on_modified(self, _=None):
        if self.input.edit_modified():
            self.input.edit_modified(False)
            self._input_changed()

    def _input_changed(self):
        text = self.input.get("1.0", "end-1c")
        if text or str(self.input.cget("state")) == "disabled":
            self.ph.place_forget()
        else:
            self.ph.place(x=self.px(16), y=self.px(12))
        if self._file_is_bin:
            meta = f"{os.path.basename(self._file_path)}, {human_size(len(self._file_bytes))}"
        elif self._file_path:
            meta = f"{os.path.basename(self._file_path)}, {len(text):,} chars"
        else:
            meta = f"{len(text):,} chars" if text else ""
        self.in_meta.configure(text=meta)
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(180, self._preview)

    def _preview(self):
        self._preview_job = None
        if self._busy:
            return
        if self._file_is_bin:
            cid = auto_detect(self._file_path, is_file=True)
        else:
            text = self.input.get("1.0", "end-1c")
            cid = None
            if text.strip():
                cid = parse_kod8(text)[0] or auto_detect(text[:2000])
        self._set_strategy_chip(cid)
        if self._rail_has_run and not self._same_as_last_run():
            self._reset_rail(list(CIPHER_LISTS[cid or "CL1"]["steps"]))

    def _snapshot(self):
        if self._file_is_bin:
            return ("file", self._file_path)
        return ("text", self.input.get("1.0", "end-1c"))

    def _same_as_last_run(self):
        return self._enc is not None and self._enc["snapshot"] == self._snapshot()

    def _clear(self):
        if self._busy:
            return
        self._file_path = self._file_bytes = None
        self._file_is_bin = False
        self._file_text_exact = self._loaded_display = None
        self._enc = None
        self._set_input("")
        self._show_nothing()
        self._reset_rail(list(CIPHER_LISTS["CL1"]["steps"]))
        self._set_strategy_chip(None)
        self._set_status("ready", "Cleared. Type or paste text, or open a file.")
        self.input.focus_set()

    # ── file open / save / copy ──────────────────────────────────────────
    def _open_file(self):
        if self._busy:
            return
        path = filedialog.askopenfilename(
            title="Open a file to encrypt or decrypt",
            filetypes=[("All files", "*.*"), ("KOD8 encrypted", "*.kod8"),
                       ("Text files", "*.txt *.md *.csv *.json"),
                       ("Images", "*.png *.jpg *.jpeg *.webp *.gif *.bmp *.svg"),
                       ("Video", "*.mp4 *.mkv *.avi *.mov *.webm *.flv"),
                       ("Documents", "*.pdf *.docx *.doc *.xlsx *.pptx *.odt")])
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            self._set_status("error", f"Couldn't open the file: {e}")
            return
        self._enc = None
        self._file_path = path
        name = os.path.basename(path)
        try:
            exact = data.decode("utf-8")
            display = exact.replace("\r\n", "\n").replace("\r", "\n")
            self._file_is_bin, self._file_bytes = False, None
            self._file_text_exact, self._loaded_display = exact, display
            self._set_input(display)
            self._set_status("ready", f"Opened {name}. Encrypt it, or decrypt if it's a .kod8 file.")
        except UnicodeDecodeError:
            self._file_is_bin, self._file_bytes = True, data
            self._file_text_exact = self._loaded_display = None
            self._set_input(f"{name}\nBinary file, {human_size(len(data))}.\n\n"
                            "Encrypt wraps the raw bytes. Decrypt restores them exactly.",
                            dim=True, locked=True)
            self._set_status("ready", f"Opened {name} ({human_size(len(data))}). Ready to encrypt.")
        self._show_nothing()
        self._reset_rail(list(CIPHER_LISTS["CL1"]["steps"]))
        self._input_changed()

    def _copy(self):
        if self._out and self._out["text"] is not None:
            self.clipboard_clear()
            self.clipboard_append(self._out["text"])
            self._set_status("ok", "Copied the output to the clipboard.")

    def _save(self):
        o = self._out
        if not o:
            return
        base = "output"
        if self._file_path:
            base = os.path.splitext(os.path.basename(self._file_path))[0]
            if base.endswith("_enc"):
                base = base[:-4]
        try:
            if o["kind"] == "enc":
                path = filedialog.asksaveasfilename(
                    title="Save encrypted output", defaultextension=".kod8",
                    initialfile=f"{base}_enc.kod8",
                    filetypes=[("KOD8 encrypted", "*.kod8"), ("All files", "*.*")])
                if not path:
                    return
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(make_header(o["cid"], o["is_bin"], o["ext"]) + "\n" + o["text"])
            else:
                name = base + (o["ext"] or ("" if o["data"] is not None else ".txt"))
                path = filedialog.asksaveasfilename(
                    title="Save decrypted output", initialfile=name,
                    defaultextension="" if (o["ext"] or o["data"] is not None) else ".txt",
                    filetypes=[("All files", "*.*"), ("Text files", "*.txt")])
                if not path:
                    return
                if o["data"] is not None:
                    with open(path, "wb") as f:
                        f.write(o["data"])
                else:
                    with open(path, "w", encoding="utf-8", newline="") as f:
                        f.write(o["text"])
            self._set_status("ok", f"Saved {os.path.basename(path)}.")
        except OSError as e:
            self._set_status("error", f"Couldn't save the file: {e}")

    # ── output area ──────────────────────────────────────────────────────
    def _set_output_text(self, text, dim=False, mint=False):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled",
                              fg=C.WELL_DIM if dim else (C.WELL_MINT if mint else C.WELL_FG))

    def _show_nothing(self):
        self._out = None
        self._set_output_text("The result appears here.", dim=True)
        self.out_meta.configure(text="")
        self.btn_copy.set_enabled(False)
        self.btn_save.set_enabled(False)

    def _show_output(self, out):
        self._out = out
        if out["data"] is not None:
            self._set_output_text(f"Binary data, {human_size(len(out['data']))}.\n"
                                  "Use Save… to write the restored file.", mint=True)
            meta = f"{out['cid']}, {len(out['data']):,} bytes"
        else:
            t = out["text"]
            shown = t if len(t) <= MAX_VIEW_CHARS else (
                t[:MAX_VIEW_CHARS] + f"\n\n… view truncated at {MAX_VIEW_CHARS:,} of "
                f"{len(t):,} characters. Save… writes everything.")
            self._set_output_text(shown, mint=(out["kind"] == "dec"))
            meta = f"{out['cid']}, {len(t):,} chars"
        self.out_meta.configure(text=meta)
        self.btn_copy.set_enabled(out["text"] is not None)
        self.btn_save.set_enabled(True)

    # ── running ──────────────────────────────────────────────────────────
    def _prepare(self, mode):
        snap = self._snapshot()
        if mode == "encrypt":
            if self._file_is_bin:
                return dict(mode=mode, text=base64.b64encode(self._file_bytes).decode("ascii"),
                            is_bin=True, cid=auto_detect(self._file_path, is_file=True),
                            ext=os.path.splitext(self._file_path)[1], snapshot=snap,
                            original=self._file_bytes)
            raw = snap[1]
            if not raw.strip():
                raise ValueError("Nothing to encrypt. Type or paste text, or open a file.")
            text = (self._file_text_exact
                    if self._file_path and raw == self._loaded_display else raw)
            ext = os.path.splitext(self._file_path)[1] if self._file_path else ""
            return dict(mode=mode, text=text, is_bin=False, cid=auto_detect(raw[:2000]),
                        ext=ext, snapshot=snap, original=text)
        # decrypt
        if self._enc is not None and self._enc["snapshot"] == snap:
            e = self._enc   # input unchanged since Encrypt: decrypt that result
            return dict(mode=mode, text=e["cipher"], is_bin=e["is_bin"], cid=e["cid"],
                        ext=e["ext"], snapshot=snap, original=e["original"])
        if self._file_is_bin:
            raise ValueError("This is a binary file, not ciphertext. "
                             "Open a .kod8 file or paste ciphertext to decrypt.")
        raw = snap[1]
        cid, is_bin, ext, body = parse_kod8(raw)
        if not body:
            raise ValueError("Nothing to decrypt. Paste ciphertext or open a .kod8 file.")
        if not cid:
            cid = self._ask_cipher_id()
            if not cid:
                raise Cancelled()
        return dict(mode=mode, text=body, is_bin=is_bin, cid=cid, ext=ext,
                    snapshot=snap, original=None)

    def _start(self, mode):
        if self._busy:
            return
        try:
            job = self._prepare(mode)
        except Cancelled:
            return
        except ValueError as e:
            self._set_status("error", str(e))
            return
        self._busy = True
        self._set_buttons(True)
        steps = list(CIPHER_LISTS[job["cid"]]["steps"])
        self._reset_rail(steps if mode == "encrypt" else list(reversed(steps)))
        self._set_strategy_chip(job["cid"])
        self._set_status("busy", "Encrypting…" if mode == "encrypt" else "Decrypting…")
        threading.Thread(target=self._worker, args=(job,), daemon=True).start()
        self.after(40, self._poll)

    def _worker(self, job):
        try:
            encrypt = job["mode"] == "encrypt"
            _, out, hist = run_kod8_pipeline(job["text"], job["is_bin"], encrypt, job["cid"])
            data = None
            if not encrypt and job["is_bin"]:
                data = base64.b64decode(out, validate=True)
            self._q.put(("ok", job, out, data, hist))
        except Exception as e:                      # noqa: BLE001 - shown to the user
            self._q.put(("err", job, str(e).removeprefix("KOD8: "), None, None))

    def _poll(self):
        try:
            msg = self._q.get_nowait()
        except queue.Empty:
            self.after(40, self._poll)
            return
        kind, job, out, data, hist = msg
        if kind == "err":
            self._busy = False
            self._set_buttons(False)
            self._reset_rail(list(CIPHER_LISTS[job["cid"]]["steps"]))
            verb = "encrypt" if job["mode"] == "encrypt" else "decrypt"
            self._set_status("error", f"Couldn't {verb}: {out}")
            return
        self._animate(job, out, data, hist)

    def _animate(self, job, out, data, hist):
        self._rail_has_run = True
        step = 135
        n = len(hist)
        for i, (fn, val) in enumerate(hist):
            self.after(i * step, self._row_active, i, fn)
            self.after(i * step + 95, self._row_done, i, val, n)
        self.after(n * step + 70, self._finish, job, out, data)

    def _row_active(self, i, fn):
        self.rows[i].set_name(fn)
        self.rows[i].set_state("active")
        self._set_progress(i)

    def _row_done(self, i, val, n):
        self.rows[i].set_state("done", val)
        self._set_progress(i + 1, n, C.RED if i + 1 < n else C.GREEN)

    def _finish(self, job, out, data):
        encrypt = job["mode"] == "encrypt"
        if encrypt:
            self._enc = dict(snapshot=job["snapshot"], cipher=out, cid=job["cid"],
                             is_bin=job["is_bin"], ext=job["ext"], original=job["original"])
            self._show_output(dict(kind="enc", text=out, data=None, cid=job["cid"],
                                   is_bin=job["is_bin"], ext=job["ext"]))
            self._set_status("ok", f"Encrypted with {job['cid']}, {STRATEGY_LABEL[job['cid']]}. "
                                   f"{len(out):,} characters of ciphertext.")
        else:
            self._show_output(dict(kind="dec", text=None if data is not None else out,
                                   data=data, cid=job["cid"], is_bin=job["is_bin"],
                                   ext=job["ext"]))
            produced = data if data is not None else out
            if job["original"] is not None and produced == job["original"]:
                msg = "Round trip verified. The output matches the original input exactly."
            else:
                size = f"{len(produced):,} bytes" if data is not None else f"{len(produced):,} characters"
                msg = f"Decrypted with {job['cid']}. {size}."
            self._set_status("ok", msg)
        self._busy = False
        self._set_buttons(False)

    # ── cipher id dialog ─────────────────────────────────────────────────
    def _ask_cipher_id(self):
        px = self.px
        dlg = tk.Toplevel(self)
        dlg.title("Choose the strategy")
        dlg.configure(bg=C.CARD)
        dlg.resizable(False, False)
        dlg.transient(self)
        pad = tk.Frame(dlg, bg=C.CARD)
        pad.pack(padx=px(24), pady=px(20))
        tk.Label(pad, text="Which strategy encrypted this?", font=self.f_card,
                 fg=C.INK, bg=C.CARD).pack(anchor="w")
        tk.Label(pad, text="The text has no .kod8 header, so the strategy can't be read from it.",
                 font=self.f_ui, fg=C.INK_DIM, bg=C.CARD).pack(anchor="w", pady=(px(4), px(12)))
        var = tk.StringVar(value="CL1")
        for cid in CIPHER_LISTS:
            tk.Radiobutton(pad, text=f"{cid}   {STRATEGY_LABEL[cid]}", variable=var, value=cid,
                           indicatoron=False, font=self.f_ui, fg=C.INK, bg=C.CARD,
                           selectcolor="#FBE4E6", activebackground="#F1F4F6",
                           activeforeground=C.INK, relief="flat", bd=0, anchor="w",
                           padx=px(12), pady=px(5), highlightthickness=0
                           ).pack(fill="x", pady=1)
        result = [None]

        def ok(_=None):
            result[0] = var.get()
            dlg.destroy()

        row = tk.Frame(pad, bg=C.CARD)
        row.pack(anchor="e", pady=(px(16), 0))
        RButton(row, self, "Cancel", dlg.destroy, "ghost", self.f_btn, padx=16, pady=8).pack(side="left")
        RButton(row, self, "Decrypt", ok, "primary", self.f_btn, padx=22, pady=8).pack(side="left", padx=(px(8), 0))
        dlg.bind("<Return>", ok)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 3
        dlg.geometry(f"+{max(0, x)}+{max(0, y)}")
        dlg.grab_set()
        dlg.wait_window()
        return result[0]


if __name__ == "__main__":
    App().mainloop()