import tkinter as tk
import tkinter.simpledialog as simpledialog
import ctypes
import os
from PIL import Image, ImageTk
import winsound
import random

BOARD_SIZE = 8
SQUARE_SIZE = 80

class ChessGame:
        def __init__(self, root, mode="pvp"):
            self.root = root
            self.root.title("Chess Game")
            self.mode = mode

            self.board = [
                ["b_rook", "b_knight", "b_bishop", "b_queen", "b_king", "b_bishop", "b_knight", "b_rook"],
                ["b_pawn"] * 8,
                [""] * 8,
                [""] * 8,
                [""] * 8,
                [""] * 8,
                ["w_pawn"] * 8,
                ["w_rook", "w_knight", "w_bishop", "w_queen", "w_king", "w_bishop", "w_knight", "w_rook"]
            ]

            self.turn = "w"
            self.selected_square = None
            self.buttons = [[None for _ in range(8)] for _ in range(8)]
            self.images = {}
            self.castling_rights = {
                'w_kingside': True, 'w_queenside': True,
                'b_kingside': True, 'b_queenside': True
            }
            self.premove = None
            self.last_double_pawn_move = None
            self.highlighted = []

            self.create_board()

        def create_board(self):
            base_size = SQUARE_SIZE
            for row in range(8):
                for col in range(8):
                    frame = tk.Frame(self.root, width=base_size, height=base_size)
                    frame.grid(row=row, column=col, sticky="nsew")
                    frame.grid_propagate(False)

                    btn = tk.Button(frame, command=lambda r=row, c=col: self.on_square_click(r, c))
                    btn.pack(expand=True, fill=tk.BOTH)

                    self.root.grid_rowconfigure(row, weight=1, uniform="equal")
                    self.root.grid_columnconfigure(col, weight=1, uniform="equal")

                    self.buttons[row][col] = btn

            self.update_board()

        def load_image(self, piece):
            if piece not in self.images:
                img = Image.open(f"pieces/{piece}.png").resize((SQUARE_SIZE, SQUARE_SIZE), Image.Resampling.LANCZOS)
                self.images[piece] = ImageTk.PhotoImage(img)
            return self.images[piece]

        def update_board(self):
            for row in range(8):
                for col in range(8):
                    piece = self.board[row][col]
                    btn = self.buttons[row][col]
                    btn.config(image="", text="")

                    color = "#b22f13" if (row + col) % 2 == 0 else "#363231"
                    btn.config(bg=color)

                    if (row, col) in self.highlighted:
                        btn.config(bg="gray")
                    if piece:
                        btn.config(image=self.load_image(piece))

        def on_square_click(self, row, col):
            self.clear_highlights()
            piece = self.board[row][col]
            if self.selected_square:
                s_row, s_col = self.selected_square
                if self.turn == self.board[s_row][s_col][0]:
                    if (row, col) in self.get_valid_moves(s_row, s_col):
                        self.move_piece(s_row, s_col, row, col)
                        self.selected_square = None
                        self.check_premove()
                    else:
                        self.selected_square = None
                else:
                    self.premove = (s_row, s_col, row, col)
                    print("Premove set.")
                    self.selected_square = None
            elif piece and piece[0] == self.turn:
                self.selected_square = (row, col)
                self.highlighted = self.get_valid_moves(row, col)
            self.update_board()

        def clear_highlights(self):
            self.highlighted = []

        def move_piece(self, sr, sc, er, ec):
            piece = self.board[sr][sc]

            if piece.endswith("_pawn") and abs(sr - er) == 2:
                self.last_double_pawn_move = (er, ec)
            else:
                self.last_double_pawn_move = None

            if piece.endswith("_pawn") and (er, ec) != (sr, sc) and self.board[er][ec] == "":
                if ec != sc:
                    self.board[sr][ec] = ""

            self.board[er][ec] = piece
            self.board[sr][sc] = ""

            if piece.endswith("_king"):
                if sc == 4 and ec == 6:
                    self.board[er][5] = f"{piece[0]}_rook"
                    self.board[er][7] = ""
                elif sc == 4 and ec == 2:
                    self.board[er][3] = f"{piece[0]}_rook"
                    self.board[er][0] = ""

            if piece == "w_king":
                self.castling_rights['w_kingside'] = False
                self.castling_rights['w_queenside'] = False
            elif piece == "b_king":
                self.castling_rights['b_kingside'] = False
                self.castling_rights['b_queenside'] = False
            elif piece == "w_rook":
                if sr == 7 and sc == 0: self.castling_rights['w_queenside'] = False
                if sr == 7 and sc == 7: self.castling_rights['w_kingside'] = False
            elif piece == "b_rook":
                if sr == 0 and sc == 0: self.castling_rights['b_queenside'] = False
                if sr == 0 and sc == 7: self.castling_rights['b_kingside'] = False

            if piece.endswith("_pawn") and (er == 0 or er == 7):
                promoted = tk.simpledialog.askstring("Promotion", "Promote to (q/r/b/n):", parent=self.root)
                promoted = promoted if promoted in ['q', 'r', 'b', 'n'] else 'q'
                self.board[er][ec] = f"{piece[0]}_" + {'q': 'queen', 'r': 'rook', 'b': 'bishop', 'n': 'knight'}[promoted]

            self.update_board()
            self.play_move_sound()
            self.turn = 'b' if self.turn == 'w' else 'w'

            enemy = self.turn
            has_moves = any(
                self.get_valid_moves(r, c)
                for r in range(8) for c in range(8)
                if self.board[r][c] and self.board[r][c][0] == enemy
            )
            if self.is_in_check(enemy):
                if not has_moves:
                    print(f"Checkmate! {piece[0].upper()} wins.")
                    response = ctypes.windll.user32.MessageBoxW(
                        0,
                        "YOU WIN BY CHECKMATE!\n\nDo you want to play again?",
                        "Game Over",
                        4
                    )
                    if response == 6:
                        self.reset_board()
                        self.update_board()
                    else:
                        self.root.quit()
                    return
            elif not has_moves:
                print("Stalemate!")
                response = ctypes.windll.user32.MessageBoxW(
                        0,
                        "STALEMATE!\n\nDo you want to play again?",
                        "Game Over",
                        4
                    )
                if response == 6:
                        self.reset_board()
                        self.update_board()
                else:
                        self.root.quit()
                return
            if self.mode == "ai" and self.turn == "b":
                self.root.after(300, self.play_random_ai_move)

        def play_move_sound(self):
            sound_path = r"\pieces\move-self.wav"
            if os.path.exists(sound_path):
                try:
                    winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                except RuntimeError as e:
                    print("Sound playback error:", e)

        def play_random_ai_move(self):
            all_moves = [
                (r, c, er, ec)
                for r in range(8)
                for c in range(8)
                if self.board[r][c] and self.board[r][c][0] == self.turn
                for (er, ec) in self.get_valid_moves(r, c)
            ]
            if all_moves:
                sr, sc, er, ec = random.choice(all_moves)
                self.move_piece(sr, sc, er, ec)

        def get_valid_moves(self, row, col, ignore_checks=False):
        
            piece = self.board[row][col]
            if not piece:
                return []

            color, type_ = piece.split("_")
            directions = []
            moves = []
            def is_valid_en_passant(self, start_row, start_col, end_row, end_col):
                piece = self.board[start_row][start_col]
                if piece[0] != "w" and piece[0] != "b":
                    return False  # Only pawns can perform en passant

                # Check if the opponent's pawn is adjacent and can capture en passant
                direction = 1 if piece[0] == "w" else -1  # White moves up, Black moves down
                if abs(start_col - end_col) == 1 and end_row == start_row + direction:
                    target_square = self.board[end_row][end_col]
                    if target_square == "":
                        opponent_pawn = self.board[start_row][end_col]
                        if opponent_pawn and opponent_pawn[0] != piece[0]:
                            return True
                return False
            def is_valid_castling(self, start_row, start_col, end_row, end_col):
                piece = self.board[start_row][start_col]
                if piece != "w_king" and piece != "b_king":
                    return False  # Only the king can castle
                
                direction = 1 if piece[0] == 'w' else -1  # White moves up, Black moves down

                # Check if the king has moved
                if self.king_has_moved(piece[0]):
                    return False
                
                # Check if the rook has moved
                rook_col = 0 if end_col == 2 else 7
                rook_piece = self.board[start_row][rook_col]
                if not rook_piece or rook_piece != f"{piece[0]}_rook":
                    return False
                
                # Check if there are no pieces between the king and the rook
                for col in range(min(start_col, end_col) + 1, max(start_col, end_col)):
                    if self.board[start_row][col] != "":
                        return False

                # Check if the squares the king will move across are not under attack
                king_path = [start_col + i for i in range(1, 3)]  # The two squares the king crosses
                for col in king_path:
                    if self.is_square_under_attack(start_row, col, piece[0]):
                        return False

                # Check if the king is not currently in check
                if self.is_king_in_check(piece[0]):
                    return False
                
                return True

            def king_has_moved(self, color):
                # Check if the king of the given color has moved
                for row in range(8):
                    for col in range(8):
                        piece = self.board[row][col]
                        if piece == f"{color}_king":
                            return piece not in self.initial_position_of_kings[color]
                return False


            if type_ == "pawn":
                direction = -1 if color == "w" else 1
                start_row = 6 if color == "w" else 1
                if self.board[row + direction][col] == "":
                    moves.append((row + direction, col))
                    if row == start_row and self.board[row + 2 * direction][col] == "":
                        moves.append((row + 2 * direction, col))
                for dc in [-1, 1]:
                    r, c = row + direction, col + dc
                    if 0 <= r < 8 and 0 <= c < 8:
                        target = self.board[r][c]
                        if target and target[0] != color:
                            moves.append((r, c))

            elif type_ == "rook":
                directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            elif type_ == "bishop":
                directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            elif type_ == "queen":
                directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
            elif type_ == "knight":
                for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                            (1, -2), (1, 2), (2, -1), (2, 1)]:
                    r, c = row + dr, col + dc
                    if 0 <= r < 8 and 0 <= c < 8:
                        target = self.board[r][c]
                        if not target or target[0] != color:
                            moves.append((r, c))
            elif type_ == "king":
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr or dc:
                            r, c = row + dr, col + dc
                            if 0 <= r < 8 and 0 <= c < 8:
                                target = self.board[r][c]
                                if not target or target[0] != color:
                                    moves.append((r, c))

                # Castling
                if color == "w" and row == 7 and col == 4:
                    if self.castling_rights['w_kingside'] and self.board[7][5] == "" and self.board[7][6] == "":
                        moves.append((7, 6))
                    if self.castling_rights['w_queenside'] and self.board[7][1] == "" and self.board[7][2] == "" and self.board[7][3] == "":
                        moves.append((7, 2))
                elif color == "b" and row == 0 and col == 4:
                    if self.castling_rights['b_kingside'] and self.board[0][5] == "" and self.board[0][6] == "":
                        moves.append((0, 6))
                    if self.castling_rights['b_queenside'] and self.board[0][1] == "" and self.board[0][2] == "" and self.board[0][3] == "":
                        moves.append((0, 2))

            # Handle sliding pieces (rook, bishop, queen)
            for dr, dc in directions:
                r, c = row + dr, col + dc
                while 0 <= r < 8 and 0 <= c < 8:
                    target = self.board[r][c]
                    if not target:
                        moves.append((r, c))
                    elif target[0] != color:
                        moves.append((r, c))
                        break
                    else:
                        break
                    r += dr
                    c += dc

            if ignore_checks:
                return moves

            # Filter moves that leave king in check
            legal = []
            for r, c in moves:
                backup = [row[:] for row in self.board]
                captured = self.board[r][c]
                self.board[r][c] = piece
                self.board[row][col] = ""
                if not self.is_in_check(color):
                    legal.append((r, c))
                self.board = [row[:] for row in backup]
            return legal

        def is_in_check(self, color):
            king_pos = None
            for r in range(8):
                for c in range(8):
                    if self.board[r][c] == f"{color}_king":
                        king_pos = (r, c)
                        break
                if king_pos:
                    break
            if not king_pos:
                return True

            enemy = 'b' if color == 'w' else 'w'
            for r in range(8):
                for c in range(8):
                    piece = self.board[r][c]
                    if piece and piece[0] == enemy:
                        if king_pos in self.get_valid_moves(r, c, ignore_checks=True):
                            return True
            return False

        def check_premove(self):
            pass

        def reset_board(self):
            self.__init__(self.root, self.mode)


def game_mode_buttons(root):
        global game  # Declare game as global to make it accessible inside the functions

        def set_mode_ai():
            global game
            game = ChessGame(root, mode="ai")  # Instantiate the game with AI mode
            print("AI mode selected")
            game_mode_frame.destroy()

        def set_mode_pvp():
            global game
            game = ChessGame(root, mode="pvp")  # Instantiate the game with PVP mode
            print("PVP mode selected")
            game_mode_frame.destroy()

        game_mode_frame = tk.Frame(root)
        game_mode_frame.grid(row=0, column=0, padx=10, pady=10)  # Use grid instead of pack

        label = tk.Label(game_mode_frame, text="Choose Mode:")
        label.grid(row=0, column=0)

        ai_button = tk.Button(game_mode_frame, text="AI", command=set_mode_ai)
        ai_button.grid(row=0, column=1, padx=5)

        pvp_button = tk.Button(game_mode_frame, text="PVP", command=set_mode_pvp)
        pvp_button.grid(row=0, column=2, padx=5)


if __name__ == "__main__":
        root = tk.Tk()
        game_mode_buttons(root)

        root.mainloop()
        game.reset()