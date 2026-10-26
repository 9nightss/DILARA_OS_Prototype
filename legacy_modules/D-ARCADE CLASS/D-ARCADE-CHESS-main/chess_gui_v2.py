import tkinter as tk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk
import threading
import time
import sys

# ═══════════════════════════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════════════════════════
BOARD_SIZE  = 8
SQUARE_SIZE = 76

TIME_CONTROLS = {
    "Bullet  1:00": 60,
    "Rapid  10:00": 600,
}
AI_DEPTH = {
    "Bullet  1:00": 1,
    "Rapid  10:00": 3,
}

# ── Board colour palettes ──────────────────────────────────────────
# Each entry: (name, light_square, dark_square)
BOARD_PALETTES = [
    ("Crimson",  "#b22f13", "#363231"),   # your original — required
    ("Classic",  "#f0d9b5", "#b58863"),   # lichess classic
    ("Slate",    "#8ca2ad", "#4a6741"),   # green felt
    ("Midnight", "#9aadbd", "#2c3e50"),   # navy dusk
]
DEFAULT_PALETTE = 0

# App chrome colours
C_BG       = "#1a1a2e"
C_PANEL    = "#16213e"
C_SIDEBAR  = "#0f1923"
C_ACCENT   = "#e94560"
C_TEXT     = "#e8dcc8"
C_SUBTEXT  = "#6b7280"
C_SELECT   = "#7ec8e3"
C_HINT     = "#a8d8a8"
C_PREMOVE  = "#e87070"
C_WARN     = "#ff6b35"
C_DBG_BG   = "#0d1117"
C_DBG_TEXT = "#39ff14"

MAX_PREMOVES = 3
COLS = "abcdefgh"

# ═══════════════════════════════════════════════════════════════════
#  PIECE TABLES
# ═══════════════════════════════════════════════════════════════════
PAWN_TABLE   = [[0,0,0,0,0,0,0,0],[50,50,50,50,50,50,50,50],[10,10,20,30,30,20,10,10],[5,5,10,25,25,10,5,5],[0,0,0,20,20,0,0,0],[5,-5,-10,0,0,-10,-5,5],[5,10,10,-20,-20,10,10,5],[0,0,0,0,0,0,0,0]]
KNIGHT_TABLE = [[-50,-40,-30,-30,-30,-30,-40,-50],[-40,-20,0,0,0,0,-20,-40],[-30,0,10,15,15,10,0,-30],[-30,5,15,20,20,15,5,-30],[-30,0,15,20,20,15,0,-30],[-30,5,10,15,15,10,5,-30],[-40,-20,0,5,5,0,-20,-40],[-50,-40,-30,-30,-30,-30,-40,-50]]
BISHOP_TABLE = [[-20,-10,-10,-10,-10,-10,-10,-20],[-10,0,0,0,0,0,0,-10],[-10,0,5,10,10,5,0,-10],[-10,5,5,10,10,5,5,-10],[-10,0,10,10,10,10,0,-10],[-10,10,10,10,10,10,10,-10],[-10,5,0,0,0,0,5,-10],[-20,-10,-10,-10,-10,-10,-10,-20]]
ROOK_TABLE   = [[0,0,0,5,5,0,0,0],[5,10,10,10,10,10,10,5],[-5,0,0,0,0,0,0,-5],[-5,0,0,0,0,0,0,-5],[-5,0,0,0,0,0,0,-5],[-5,0,0,0,0,0,0,-5],[-5,0,0,0,0,0,0,-5],[0,0,0,5,5,0,0,0]]
QUEEN_TABLE  = [[-20,-10,-10,-5,-5,-10,-10,-20],[-10,0,0,0,0,0,0,-10],[-10,0,5,5,5,5,0,-10],[-5,0,5,5,5,5,0,-5],[0,0,5,5,5,5,0,-5],[-10,5,5,5,5,5,0,-10],[-10,0,5,0,0,0,0,-10],[-20,-10,-10,-5,-5,-10,-10,-20]]
KING_TABLE   = [[-30,-40,-40,-50,-50,-40,-40,-30],[-30,-40,-40,-50,-50,-40,-40,-30],[-30,-40,-40,-50,-50,-40,-40,-30],[-30,-40,-40,-50,-50,-40,-40,-30],[-20,-30,-30,-40,-40,-30,-30,-20],[-10,-20,-20,-20,-20,-20,-20,-10],[20,20,0,0,0,0,20,20],[20,30,10,0,0,10,30,20]]
PIECE_VALUES = {'pawn':100,'knight':320,'bishop':330,'rook':500,'queen':900,'king':20000}
TABLES = {"pawn":PAWN_TABLE,"knight":KNIGHT_TABLE,"bishop":BISHOP_TABLE,
          "rook":ROOK_TABLE,"queen":QUEEN_TABLE,"king":KING_TABLE}

# ═══════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════
def to_algebraic(r, c):
    return f"{COLS[c]}{8 - r}"

def board_to_fen(board):
    rows = []
    for r in range(8):
        empty, row_str = 0, ""
        for c in range(8):
            p = board[r][c]
            if not p:
                empty += 1
            else:
                if empty: row_str += str(empty); empty = 0
                clr, typ = p.split("_")
                sym = {"pawn":"p","knight":"n","bishop":"b","rook":"r","queen":"q","king":"k"}[typ]
                row_str += sym.upper() if clr=='w' else sym
        if empty: row_str += str(empty)
        rows.append(row_str)
    return "/".join(rows)

def play_sound(freq=500, dur=50):
    try:
        if sys.platform == "win32":
            import winsound
            winsound.Beep(freq, dur)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════
#  MODE SELECTION
# ═══════════════════════════════════════════════════════════════════
class ModeScreen:
    def __init__(self, root, on_start):
        self.root     = root
        self.on_start = on_start
        self.frame    = tk.Frame(root, bg=C_BG)
        self.frame.pack(fill="both", expand=True)

        tk.Label(self.frame, text="♟  CHESS AI", bg=C_BG, fg=C_TEXT,
                 font=("Courier New", 26, "bold")).pack(pady=(36, 4))
        tk.Label(self.frame, text="select time control", bg=C_BG, fg=C_SUBTEXT,
                 font=("Courier New", 9)).pack(pady=(0, 20))

        self.selected_tc = tk.StringVar(value=list(TIME_CONTROLS.keys())[0])
        for label in TIME_CONTROLS:
            tk.Radiobutton(
                self.frame, text=label, variable=self.selected_tc, value=label,
                bg=C_BG, fg=C_TEXT, selectcolor=C_PANEL, activebackground=C_BG,
                font=("Courier New", 12, "bold"), indicatoron=0,
                relief="flat", bd=0, padx=20, pady=9, cursor="hand2",
                highlightthickness=1, highlightbackground="#2a2a3a"
            ).pack(fill="x", padx=56, pady=5)

        tk.Button(
            self.frame, text="START  ▶", command=self._start,
            bg=C_ACCENT, fg="white", font=("Courier New", 11, "bold"),
            relief="flat", cursor="hand2", activebackground="#c73652",
            padx=20, pady=10
        ).pack(pady=24, padx=56, fill="x")

    def _start(self):
        tc = self.selected_tc.get()
        self.frame.destroy()
        ChessGame(self.root, tc)

# ═══════════════════════════════════════════════════════════════════
#  CLOCK WIDGET
# ═══════════════════════════════════════════════════════════════════
class ClockWidget(tk.Frame):
    def __init__(self, parent, label, fg_color, **kw):
        super().__init__(parent, bg=C_SIDEBAR, **kw)
        tk.Label(self, text=label, bg=C_SIDEBAR, fg=C_SUBTEXT,
                 font=("Courier New", 7, "bold")).pack(pady=(6,0))
        self.time_lbl = tk.Label(self, text="00:00.0", bg=C_SIDEBAR,
                                  fg=fg_color, font=("Courier New", 19, "bold"))
        self.time_lbl.pack(pady=(0,6))
        self._base_fg = fg_color
        
    def update_display(self, secs):
        secs  = max(0.0, secs)
        m, s  = int(secs)//60, int(secs)%60
        tenth = int((secs - int(secs)) * 10)
        color = C_WARN if secs <= 10 else self._base_fg
        self.time_lbl.config(text=f"{m:02d}:{s:02d}.{tenth}", fg=color)

    def set_active(self, active):
        """Highlight the active clock with a subtle border effect."""
        bg = "#1a2a1a" if active else C_SIDEBAR
        self.config(bg=bg)
        self.time_lbl.config(bg=bg)
        for w in self.winfo_children():
            try: w.config(bg=bg)
            except: pass

# ═══════════════════════════════════════════════════════════════════
#  DEBUG PANEL
# ═══════════════════════════════════════════════════════════════════
class DebugPanel:
    WIDTH = 240

    def __init__(self, parent):
        self.visible = False
        self.frame   = tk.Frame(parent, bg=C_DBG_BG, width=0)
        self.frame.pack_propagate(False)

        hdr = tk.Frame(self.frame, bg="#0a0e13")
        hdr.pack(fill="x")
        tk.Label(hdr, text="◈  DEBUG LOG", bg="#0a0e13", fg=C_DBG_TEXT,
                 font=("Courier New", 9, "bold")).pack(side="left", padx=8, pady=5)

        txt_wrap = tk.Frame(self.frame, bg=C_DBG_BG)
        txt_wrap.pack(fill="both", expand=True, padx=3, pady=3)
        sb = tk.Scrollbar(txt_wrap); sb.pack(side="right", fill="y")
        self.text = tk.Text(
            txt_wrap, bg=C_DBG_BG, fg=C_DBG_TEXT,
            font=("Courier New", 7), relief="flat", bd=0,
            wrap="word", state="disabled", yscrollcommand=sb.set
        )
        self.text.pack(fill="both", expand=True)
        sb.config(command=self.text.yview)
        self.text.tag_config("hdr",  foreground="#ffffff")
        self.text.tag_config("val",  foreground=C_DBG_TEXT)
        self.text.tag_config("warn", foreground=C_WARN)
        self.text.tag_config("move", foreground=C_SELECT)
        self.text.tag_config("fen",  foreground="#555")
        self.text.tag_config("sep",  foreground="#222")

        tk.Button(self.frame, text="CLEAR", command=self.clear,
                  bg="#111", fg="#444", font=("Courier New", 7),
                  relief="flat", cursor="hand2").pack(fill="x", padx=3, pady=(0,3))

    def show(self):
        self.visible = True
        self.frame.config(width=self.WIDTH)
        self.frame.pack(side="right", fill="y")

    def hide(self):
        self.visible = False
        self.frame.pack_forget()

    def log(self, entries, tag_map=None):
        self.text.config(state="normal")
        self.text.insert("end", "─"*30+"\n", "sep")
        self.text.insert("end", f"  {time.strftime('%H:%M:%S')}\n", "hdr")
        for k, v in entries.items():
            tag = (tag_map or {}).get(k, "val")
            self.text.insert("end", f"  {k:<16}", "hdr")
            self.text.insert("end", f"{v}\n", tag)
        self.text.config(state="disabled")
        self.text.see("end")

    def log_error(self, msg):
        self.text.config(state="normal")
        self.text.insert("end", f"  ⚠ {msg}\n", "warn")
        self.text.config(state="disabled")
        self.text.see("end")

    def clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")

# ═══════════════════════════════════════════════════════════════════
#  SIDEBAR PANEL  (right of board — always visible)
# ═══════════════════════════════════════════════════════════════════
class SidePanel(tk.Frame):
    """
    Contains: clocks, status, palette switcher, action buttons.
    Lives to the RIGHT of the board — no controls below the board.
    """
    WIDTH = 170

    def __init__(self, parent, game_ref):
        super().__init__(parent, bg=C_SIDEBAR, width=self.WIDTH)
        self.pack_propagate(False)
        self.game = game_ref
        self._build()

    def _build(self):
        g = self.game

        # ── Clocks ────────────────────────────────────────────────
        clk_frame = tk.Frame(self, bg=C_SIDEBAR)
        clk_frame.pack(fill="x", padx=6, pady=(10,4))

        g.black_clock = ClockWidget(clk_frame, "BLACK ▲", "#c9a96e")
        g.black_clock.pack(fill="x", pady=(0,4))
        g.white_clock = ClockWidget(clk_frame, "WHITE ▼", "#e8dcc8")
        g.white_clock.pack(fill="x")

        # ── Divider ───────────────────────────────────────────────
        tk.Frame(self, bg="#1e2a3a", height=1).pack(fill="x", padx=6, pady=6)

        # ── Status ────────────────────────────────────────────────
        g.status_label = tk.Label(
            self, text="", bg=C_SIDEBAR, fg=C_TEXT,
            font=("Courier New", 9, "bold"), wraplength=150, justify="left"
        )
        g.status_label.pack(fill="x", padx=10, pady=(0,2))

        # Premove indicator
        g.premove_label = tk.Label(
            self, text="", bg=C_SIDEBAR, fg=C_PREMOVE,
            font=("Courier New", 7), wraplength=150, justify="left"
        )
        g.premove_label.pack(fill="x", padx=10, pady=(0,4))

        # ── Divider ───────────────────────────────────────────────
        tk.Frame(self, bg="#1e2a3a", height=1).pack(fill="x", padx=6, pady=4)

        # ── Board palette ─────────────────────────────────────────
        tk.Label(self, text="BOARD THEME", bg=C_SIDEBAR, fg=C_SUBTEXT,
                 font=("Courier New", 7, "bold")).pack(padx=10, anchor="w", pady=(2,4))

        self._palette_btns = []
        for i, (name, light, dark) in enumerate(BOARD_PALETTES):
            row = tk.Frame(self, bg=C_SIDEBAR)
            row.pack(fill="x", padx=8, pady=2)

            # Two colour swatches
            swatch_frame = tk.Frame(row, bg=C_SIDEBAR)
            swatch_frame.pack(side="left")
            tk.Frame(swatch_frame, bg=light, width=12, height=12).pack(side="left", padx=(0,1))
            tk.Frame(swatch_frame, bg=dark,  width=12, height=12).pack(side="left", padx=(0,4))

            btn = tk.Button(
                row, text=name, command=lambda idx=i: g._set_palette(idx),
                bg="#1a2233", fg=C_TEXT, font=("Courier New", 8),
                relief="flat", cursor="hand2", anchor="w",
                activebackground="#263040", bd=0, padx=4, pady=3
            )
            btn.pack(side="left", fill="x", expand=True)
            self._palette_btns.append(btn)

        self.highlight_palette(DEFAULT_PALETTE)

        # ── Divider ───────────────────────────────────────────────
        tk.Frame(self, bg="#1e2a3a", height=1).pack(fill="x", padx=6, pady=6)

        # ── Action buttons ────────────────────────────────────────
        def _btn(text, cmd, bg, fg=C_TEXT):
            tk.Button(
                self, text=text, command=cmd,
                bg=bg, fg=fg, font=("Courier New", 8, "bold"),
                relief="flat", cursor="hand2",
                activebackground=bg, bd=0
            ).pack(fill="x", padx=8, pady=3, ipady=5)

        _btn("⟳  NEW GAME",  g.reset_game,      C_ACCENT, "white")
        _btn("◈  DEBUG",     g._toggle_debug,   "#1e2a1e", C_DBG_TEXT)
        _btn("⇦  MENU",      g._back_to_menu,   "#252535")

        # Spacer
        tk.Frame(self, bg=C_SIDEBAR).pack(fill="both", expand=True)

        # Time control label at bottom
        tk.Label(self, text=g.tc_label, bg=C_SIDEBAR, fg=C_SUBTEXT,
                 font=("Courier New", 7)).pack(pady=(0,8))

    def highlight_palette(self, idx):
        for i, btn in enumerate(self._palette_btns):
            btn.config(
                bg="#2a3d55" if i == idx else "#1a2233",
                fg="white"   if i == idx else C_TEXT
            )

# ═══════════════════════════════════════════════════════════════════
#  CHESS GAME
# ═══════════════════════════════════════════════════════════════════
class ChessGame:
    def __init__(self, root, time_control_label):
        self.root      = root
        self.tc_label  = time_control_label
        self.tc_secs   = TIME_CONTROLS[time_control_label]
        self.ai_depth  = AI_DEPTH[time_control_label]
        self.images    = {}
        self.trans_table = {}

        self._ai_thinking  = False
        self._clock_job    = None
        self._game_over    = False
        self._premove_queue   = []
        self._premove_pending = None
        self._clock_anchor    = None
        self._white_remaining = float(self.tc_secs)
        self._black_remaining = float(self.tc_secs)
        self._move_history    = []
        self._move_number     = 1

        # Active palette index + resolved colours
        self._palette_idx = DEFAULT_PALETTE
        self._c_light, self._c_dark = (
            BOARD_PALETTES[DEFAULT_PALETTE][1],
            BOARD_PALETTES[DEFAULT_PALETTE][2]
        )

        # Placeholder attrs filled by SidePanel
        self.black_clock   = None
        self.white_clock   = None
        self.status_label  = None
        self.premove_label = None

        self._build_ui()
        self.reset_game()

    # ── UI BUILD ────────────────────────────────────────────────────

    def _build_ui(self):
        # Root container: board | sidebar | (debug hidden)
        self.outer = tk.Frame(self.root, bg=C_BG)
        self.outer.pack(fill="both", expand=True)

        # ── Board area (left) ──────────────────────────────────────
        board_wrap = tk.Frame(self.outer, bg=C_BG)
        board_wrap.pack(side="left", padx=(8,0), pady=8)

        # Rank/file labels + board grid
        self.board_frame = tk.Frame(board_wrap, bg=C_BG)
        self.board_frame.pack()

        for i in range(8):
            self.board_frame.grid_rowconfigure(i, minsize=SQUARE_SIZE)
            self.board_frame.grid_columnconfigure(i, minsize=SQUARE_SIZE)

        self.buttons = [[None]*8 for _ in range(8)]
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                btn = tk.Button(
                    self.board_frame,
                    command=lambda r=r, c=c: self.on_square_click(r, c),
                    relief="flat", bd=0
                )
                btn.grid(row=r, column=c, sticky="nsew")
                self.buttons[r][c] = btn

        # File labels below board
        file_row = tk.Frame(board_wrap, bg=C_BG)
        file_row.pack(fill="x")
        for i, ch in enumerate("abcdefgh"):
            tk.Label(file_row, text=ch, bg=C_BG, fg=C_SUBTEXT,
                     font=("Courier New", 7), width=SQUARE_SIZE//8
                     ).pack(side="left", expand=True)

        # ── Side panel (middle) ────────────────────────────────────
        self.side = SidePanel(self.outer, self)
        self.side.pack(side="left", fill="y", padx=(6,4), pady=8)

        # ── Debug panel (rightmost, hidden) ───────────────────────
        self.debug = DebugPanel(self.outer)
        # Note: debug.frame is NOT packed until toggled

    def _toggle_debug(self):
        if self.debug.visible:
            self.debug.hide()
        else:
            self.debug.show()

    def _set_palette(self, idx):
        self._palette_idx = idx
        self._c_light = BOARD_PALETTES[idx][1]
        self._c_dark  = BOARD_PALETTES[idx][2]
        self.side.highlight_palette(idx)
        self.update_visuals()

    # ── RESET ───────────────────────────────────────────────────────

    def reset_game(self):
        if self._clock_job:
            self.root.after_cancel(self._clock_job)
            self._clock_job = None

        self.board = [
            ["b_rook","b_knight","b_bishop","b_queen","b_king","b_bishop","b_knight","b_rook"],
            ["b_pawn"]*8, [""]*8, [""]*8, [""]*8, [""]*8, ["w_pawn"]*8,
            ["w_rook","w_knight","w_bishop","w_queen","w_king","w_bishop","w_knight","w_rook"]
        ]
        self.turn             = "w"
        self.selected_square  = None
        self.highlighted      = []
        self.has_moved = {
            'w_king':False,'b_king':False,
            'w_rook_0':False,'w_rook_7':False,
            'b_rook_0':False,'b_rook_7':False
        }
        self._white_remaining = float(self.tc_secs)
        self._black_remaining = float(self.tc_secs)
        self._clock_anchor    = time.time()
        self._game_over       = False
        self._ai_thinking     = False
        self._premove_queue   = []
        self._premove_pending = None
        self._move_history    = []
        self._move_number     = 1
        self.trans_table      = {}

        self.white_clock.update_display(self._white_remaining)
        self.black_clock.update_display(self._black_remaining)
        self.white_clock.set_active(True)
        self.black_clock.set_active(False)
        self._set_status("White's Turn")
        self._update_premove_label()
        self.update_visuals()
        self._tick()

    def _back_to_menu(self):
        if self._clock_job:
            self.root.after_cancel(self._clock_job)
        for w in self.root.winfo_children():
            w.destroy()
        ModeScreen(self.root, lambda tc: ChessGame(self.root, tc))

    # ── CLOCK ───────────────────────────────────────────────────────

    def _tick(self):
        if self._game_over: return
        now   = time.time()
        delta = now - self._clock_anchor
        self._clock_anchor = now

        if self.turn == 'w' and not self._ai_thinking:
            self._white_remaining -= delta
            if self._white_remaining <= 0:
                self._white_remaining = 0
                self.white_clock.update_display(0)
                self._timeout('w'); return
            self.white_clock.update_display(self._white_remaining)

        elif self.turn == 'b' and not self._ai_thinking:
            self._black_remaining -= delta
            if self._black_remaining <= 0:
                self._black_remaining = 0
                self.black_clock.update_display(0)
                self._timeout('b'); return
            self.black_clock.update_display(self._black_remaining)

        self._clock_job = self.root.after(100, self._tick)

    def _reset_anchor(self):
        self._clock_anchor = time.time()

    def _timeout(self, color):
        self._game_over = True
        play_sound(300, 200)
        winner = "Black" if color=='w' else "White"
        loser  = "White" if color=='w' else "Black"
        self._set_status(f"⏱  {loser} loses on time!")
        self.debug.log({"EVENT":"TIMEOUT","loser":loser}, {"EVENT":"warn"})
        messagebox.showinfo("Time Out", f"{loser} ran out of time!\n{winner} wins.")

    # ── VISUALS ─────────────────────────────────────────────────────

    def load_image(self, piece):
        if piece not in self.images:
            img = Image.open(f"pieces/{piece}.png").resize(
                (SQUARE_SIZE-8, SQUARE_SIZE-8), Image.Resampling.LANCZOS
            )
            self.images[piece] = ImageTk.PhotoImage(img)
        return self.images[piece]

    def update_visuals(self):
        premove_sq = set()
        for pm in self._premove_queue:
            premove_sq.add((pm[0],pm[1])); premove_sq.add((pm[2],pm[3]))

        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if self.selected_square == (r,c):       col = C_SELECT
                elif (r,c) in self.highlighted:          col = C_HINT
                elif (r,c) in premove_sq:                col = C_PREMOVE
                elif (r+c)%2 == 0:                       col = self._c_light
                else:                                    col = self._c_dark

                self.buttons[r][c].config(bg=col, activebackground=col, image="")
                if piece:
                    try:    self.buttons[r][c].config(image=self.load_image(piece))
                    except: self.buttons[r][c].config(text=piece.split("_")[1][0].upper())

    def _set_status(self, text):
        self.status_label.config(text=text)

    def _update_premove_label(self):
        if self._premove_queue:
            s = "  ".join(f"{to_algebraic(m[0],m[1])}→{to_algebraic(m[2],m[3])}"
                          for m in self._premove_queue)
            self.premove_label.config(text=f"PRE: {s}")
        else:
            self.premove_label.config(text="")

    def _update_clock_active(self):
        self.white_clock.set_active(self.turn=='w' and not self._ai_thinking)
        self.black_clock.set_active(self.turn=='b' or self._ai_thinking)

    # ── MOVE GENERATION ─────────────────────────────────────────────

    def get_raw_moves(self, r, c, board):
        piece = board[r][c]
        if not piece: return []
        color, p_type = piece.split("_")
        moves = []
        if p_type == "pawn":
            fwd = -1 if color=='w' else 1
            if 0<=r+fwd<8 and not board[r+fwd][c]:
                moves.append((r+fwd,c))
                start = 6 if color=='w' else 1
                if r==start and not board[r+2*fwd][c]: moves.append((r+2*fwd,c))
            for dc in [-1,1]:
                nr,nc=r+fwd,c+dc
                if 0<=nr<8 and 0<=nc<8:
                    t=board[nr][nc]
                    if t and not t.startswith(color): moves.append((nr,nc))
        elif p_type=="knight":
            for dr,dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
                nr,nc=r+dr,c+dc
                if 0<=nr<8 and 0<=nc<8:
                    if not board[nr][nc] or not board[nr][nc].startswith(color):
                        moves.append((nr,nc))
        elif p_type=="king":
            for dr in [-1,0,1]:
                for dc in [-1,0,1]:
                    nr,nc=r+dr,c+dc
                    if 0<=nr<8 and 0<=nc<8 and (dr or dc):
                        if not board[nr][nc] or not board[nr][nc].startswith(color):
                            moves.append((nr,nc))
        else:
            dirs=([(0,1),(0,-1),(1,0),(-1,0)] if p_type=="rook"
                  else [(1,1),(1,-1),(-1,1),(-1,-1)] if p_type=="bishop"
                  else [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)])
            for dr,dc in dirs:
                nr,nc=r+dr,c+dc
                while 0<=nr<8 and 0<=nc<8:
                    if not board[nr][nc]: moves.append((nr,nc))
                    elif not board[nr][nc].startswith(color): moves.append((nr,nc)); break
                    else: break
                    nr,nc=nr+dr,nc+dc
        return moves

    def is_attacked(self, r, c, color, board):
        opp='b' if color=='w' else 'w'
        for row in range(8):
            for col in range(8):
                if board[row][col] and board[row][col].startswith(opp):
                    if (r,c) in self.get_raw_moves(row,col,board): return True
        return False

    def is_in_check(self, color, board):
        kp=next(((r,c) for r in range(8) for c in range(8) if board[r][c]==f"{color}_king"),None)
        return self.is_attacked(kp[0],kp[1],color,board) if kp else False

    def get_legal_moves(self, color, board):
        legal=[]
        for r in range(8):
            for c in range(8):
                if board[r][c] and board[r][c].startswith(color):
                    for er,ec in self.get_raw_moves(r,c,board):
                        tmp=[row[:] for row in board]; tmp[er][ec],tmp[r][c]=tmp[r][c],""
                        if not self.is_in_check(color,tmp): legal.append((r,c,er,ec))
        row=7 if color=='w' else 0
        if not self.has_moved[f'{color}_king'] and not self.is_in_check(color,board):
            if (not self.has_moved[f'{color}_rook_7'] and not board[row][5] and not board[row][6]
                    and not self.is_attacked(row,5,color,board)
                    and not self.is_attacked(row,6,color,board)):
                legal.append((row,4,row,6))
            if (not self.has_moved[f'{color}_rook_0'] and not board[row][1]
                    and not board[row][2] and not board[row][3]
                    and not self.is_attacked(row,2,color,board)
                    and not self.is_attacked(row,3,color,board)):
                legal.append((row,4,row,2))
        return legal

    # ── APPLY MOVE ──────────────────────────────────────────────────

    def apply_move(self, sr, sc, er, ec, silent=False):
        p = self.board[sr][sc]
        move_str = f"{to_algebraic(sr,sc)}{to_algebraic(er,ec)}"
        if p.endswith("_king") and abs(ec-sc)==2:
            rsk,rek=(7,5) if ec==6 else (0,3)
            self.board[sr][rek]=self.board[sr][rsk]; self.board[sr][rsk]=""
        if p=="w_king":   self.has_moved['w_king']=True
        elif p=="b_king": self.has_moved['b_king']=True
        elif p.endswith("_rook"):
            key=f"{p[0]}_rook_{sc}"
            if key in self.has_moved: self.has_moved[key]=True
        self.board[er][ec]=p; self.board[sr][sc]=""
        if p.endswith("_pawn") and (er==0 or er==7):
            color=p[0]
            if not silent and color=='w':
                choice=simpledialog.askstring("Promotion","Promote to (queen/rook/bishop/knight):")
                piece=choice if choice in ['queen','rook','bishop','knight'] else 'queen'
            else:
                piece='queen'
            self.board[er][ec]=f"{color}_{piece}"; move_str+=piece[0]
        if not silent: play_sound(500,50)
        return move_str

    def check_game_over(self):
        nt='b' if self.turn=='w' else 'w'
        if not self.get_legal_moves(nt,self.board):
            if self.is_in_check(nt,self.board):
                msg=f"Checkmate! {'White' if nt=='b' else 'Black'} wins."
            else:
                msg="Stalemate! Draw."
            self._game_over=True
            self._set_status(msg)
            messagebox.showinfo("Game Over",msg)
            return True
        return False

    # ── EVALUATION ──────────────────────────────────────────────────

    def _pawn_score(self, own, opp):
        s=0
        for c in own:
            if own.count(c)>1: s-=20
            if (c-1) not in own and (c+1) not in own: s-=15
            if all(f not in opp for f in [x for x in [c-1,c,c+1] if 0<=x<8]): s+=30
        return s

    def _king_score(self, color, kpos, board, pcols):
        s=0; opp='b' if color=='w' else 'w'; kr,kc=kpos
        sr2=kr-1 if color=='w' else kr+1
        if 0<=sr2<8:
            for dc in [-1,0,1]:
                nc=kc+dc
                if 0<=nc<8 and board[sr2][nc]==f"{color}_pawn": s+=15
        if kc not in pcols: s-=25
        for r in range(8):
            for c in range(8):
                pc=board[r][c]
                if pc and pc.startswith(opp) and not pc.endswith("_pawn"):
                    d=max(abs(r-kr),abs(c-kc))
                    if d<=2: s-=(3-d)*10
        return s

    def evaluate(self, b):
        s=0; wp=[]; bp=[]; wk=bk=None
        for r in range(8):
            for c in range(8):
                p=b[r][c]
                if not p: continue
                clr,typ=p.split("_")
                val=PIECE_VALUES[typ]+TABLES[typ][r if clr=='w' else (7-r)][c]
                s+=val if clr=='w' else -val
                if typ=='pawn': (wp if clr=='w' else bp).append(c)
                if typ=='king':
                    if clr=='w': wk=(r,c)
                    else: bk=(r,c)
        s+=self._pawn_score(wp,bp); s-=self._pawn_score(bp,wp)
        if wk: s+=self._king_score('w',wk,b,wp)
        if bk: s-=self._king_score('b',bk,b,bp)
        return s

    # ── QUIESCENCE ──────────────────────────────────────────────────

    def quiescence(self, board, alpha, beta, maximizing):
        sp=self.evaluate(board); D=900
        if maximizing:
            if sp>=beta: return beta
            if sp<alpha-D: return alpha
            alpha=max(alpha,sp)
        else:
            if sp<=alpha: return alpha
            if sp>beta+D: return beta
            beta=min(beta,sp)
        color='w' if maximizing else 'b'
        caps=sorted(
            [m for m in self.get_legal_moves(color,board) if board[m[2]][m[3]]],
            key=lambda m: PIECE_VALUES[board[m[2]][m[3]].split("_")[1]]-
                          PIECE_VALUES[board[m[0]][m[1]].split("_")[1]],
            reverse=True
        )
        for m in caps:
            tmp=[row[:] for row in board]; tmp[m[2]][m[3]],tmp[m[0]][m[1]]=tmp[m[0]][m[1]],""
            sc2=self.quiescence(tmp,alpha,beta,not maximizing)
            if maximizing: alpha=max(alpha,sc2); (bt:=beta) if False else None
            else:          beta=min(beta,sc2)
            if beta<=alpha: break
        return alpha if maximizing else beta

    # ── MINIMAX ─────────────────────────────────────────────────────

    def _order(self, moves, board):
        def s(m):
            v=board[m[2]][m[3]]; a=board[m[0]][m[1]]
            return (PIECE_VALUES[v.split("_")[1]]-PIECE_VALUES[a.split("_")[1]]) if v else 0
        return sorted(moves,key=s,reverse=True)

    def minimax(self, b, d, a, bt, maximizing, stats):
        key=(tuple(tuple(r) for r in b),d,maximizing)
        if key in self.trans_table: return self.trans_table[key]
        if d==0:
            stats['nodes']+=1
            r=(self.quiescence(b,a,bt,maximizing),None)
            self.trans_table[key]=r; return r
        color='w' if maximizing else 'b'
        moves=self.get_legal_moves(color,b)
        if not moves:
            r=(self.evaluate(b),None); self.trans_table[key]=r; return r
        moves=self._order(moves,b); best_m=None
        if maximizing:
            mv=-1e9
            for m in moves:
                stats['nodes']+=1
                tmp=[row[:] for row in b]; tmp[m[2]][m[3]],tmp[m[0]][m[1]]=tmp[m[0]][m[1]],""
                v=self.minimax(tmp,d-1,a,bt,False,stats)[0]
                if v>mv: mv,best_m=v,m
                a=max(a,v)
                if bt<=a: break
            r=(mv,best_m)
        else:
            mv=1e9
            for m in moves:
                stats['nodes']+=1
                tmp=[row[:] for row in b]; tmp[m[2]][m[3]],tmp[m[0]][m[1]]=tmp[m[0]][m[1]],""
                v=self.minimax(tmp,d-1,a,bt,True,stats)[0]
                if v<mv: mv,best_m=v,m
                bt=min(bt,v)
                if bt<=a: break
            r=(mv,best_m)
        self.trans_table[key]=r; return r

    # ── AI TURN ─────────────────────────────────────────────────────

    def ai_move(self):
        if self._game_over: return
        self._ai_thinking=True
        self._reset_anchor()
        self._update_clock_active()
        self._set_status("◌ thinking...")

        def think():
            t0=time.time(); stats={'nodes':0}
            try:
                self.trans_table={}
                score,best=self.minimax(self.board,self.ai_depth,-1e9,1e9,False,stats)
            except Exception as e:
                self.root.after(0,lambda: self.debug.log_error(str(e)))
                self.root.after(0,lambda: self._finish_ai_move(None,0,0,0))
                return
            elapsed=time.time()-t0
            self.root.after(0,lambda: self._finish_ai_move(best,score,elapsed,stats['nodes']))

        threading.Thread(target=think,daemon=True).start()

    def _finish_ai_move(self, best, score, elapsed, nodes):
        if self._game_over: return
        move_str=""
        if best:
            move_str=self.apply_move(*best,silent=False)
            self._move_history.append((f"{self._move_number}.","..."+move_str+"(AI)",round(score)))
            self._move_number+=1

        fen=board_to_fen(self.board)
        hist="\n".join(f"  {n} {m}" for n,m,_ in self._move_history[-6:])
        self.debug.log({
            "depth":str(self.ai_depth),"nodes":f"{nodes:,}",
            "think(s)":f"{elapsed:.3f}","eval":f"{score:+.0f}",
            "move":move_str or "none","FEN":fen,"history":"\n"+hist,
        },{"eval":"warn" if abs(score)>500 else "val","move":"move","FEN":"fen","history":"move"})

        self.turn='w'; self._ai_thinking=False; self._reset_anchor()
        self._update_clock_active()
        self.update_visuals()
        if not self.check_game_over():
            self._set_status("White's Turn")
            self._execute_premoves()

    # ── PREMOVES ────────────────────────────────────────────────────

    def _execute_premoves(self):
        while self._premove_queue and not self._game_over:
            sr,sc,er,ec=self._premove_queue[0]
            legal=self.get_legal_moves('w',self.board)
            if (sr,sc,er,ec) in legal:
                self._premove_queue.pop(0)
                move_str=self.apply_move(sr,sc,er,ec)
                self._move_history.append((f"{self._move_number}.",move_str,0))
                self.turn='b'; self._reset_anchor()
                self.update_visuals(); self._update_premove_label()
                if not self.check_game_over():
                    self._set_status("Black's Turn")
                    self.root.after(200,self.ai_move)
                return
            else:
                self.debug.log(
                    {"PREMOVE":f"invalid {to_algebraic(sr,sc)}→{to_algebraic(er,ec)}, cleared"},
                    {"PREMOVE":"warn"})
                self._premove_queue.clear(); break
        self._update_premove_label()

    # ── PLAYER INPUT ────────────────────────────────────────────────

    def on_square_click(self, r, c):
        if self._game_over: return

        # PREMOVE MODE
        if self._ai_thinking:
            if self._premove_pending is None:
                if self.board[r][c] and self.board[r][c].startswith('w'):
                    self._premove_pending=(r,c)
                    self.highlighted=[(er,ec) for sr2,sc2,er,ec
                                      in self.get_legal_moves('w',self.board)
                                      if sr2==r and sc2==c]
                    self.update_visuals()
            else:
                sr2,sc2=self._premove_pending
                if len(self._premove_queue)<MAX_PREMOVES:
                    self._premove_queue.append((sr2,sc2,r,c))
                    self.debug.log(
                        {"PREMOVE queued":f"{to_algebraic(sr2,sc2)}→{to_algebraic(r,c)}",
                         "queue depth":str(len(self._premove_queue))},
                        {"PREMOVE queued":"move"})
                self._premove_pending=None; self.highlighted=[]
                self._update_premove_label(); self.update_visuals()
            return

        if self.turn!='w': return
        legal=self.get_legal_moves(self.turn,self.board)

        if self.selected_square:
            sr,sc=self.selected_square
            if (sr,sc,r,c) in legal:
                move_str=self.apply_move(sr,sc,r,c)
                self._move_history.append((f"{self._move_number}.",move_str,0))
                self.turn='b'; self.selected_square=None; self.highlighted=[]
                self._reset_anchor(); self._update_clock_active()
                self.update_visuals()
                if not self.check_game_over():
                    self._set_status("Black's Turn")
                    self.root.after(200,self.ai_move)
            else:
                self.selected_square=None; self.highlighted=[]
                self.on_square_click(r,c)
        elif self.board[r][c] and self.board[r][c].startswith(self.turn):
            self.selected_square=(r,c)
            self.highlighted=[(m[2],m[3]) for m in legal if m[0]==r and m[1]==c]

        self.update_visuals()

# ═══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Chess AI v5 — Speed Edition")
    root.configure(bg=C_BG)
    root.resizable(False, False)
    ModeScreen(root, lambda tc: ChessGame(root, tc))
    root.mainloop()