import tkinter as tk
from tkinter import messagebox

class TicTacToe:
    def __init__(self, root):
        self.root = root
        self.root.title("Unbeatable AI Tic-Tac-Toe")
        self.board = [""] * 9
        self.buttons = []
        self.human = "X"
        self.ai = "O"
        self.create_widgets()

    def create_widgets(self):
        for i in range(9):
            btn = tk.Button(self.root, text="", font=('Arial', 24, 'bold'), width=5, height=2,
                            command=lambda i=i: self.human_move(i))
            btn.grid(row=i//3, column=i%3)
            self.buttons.append(btn)
        
        # Reset button
        tk.Button(self.root, text="Restart", command=self.reset).grid(row=3, column=0, columnspan=3, sticky="nsew")

    def human_move(self, i):
        if self.board[i] == "" and not self.check_winner(self.board):
            self.make_move(i, self.human)
            if not self.check_winner(self.board) and "" in self.board:
                self.ai_move()

    def make_move(self, i, player):
        self.board[i] = player
        self.buttons[i].config(text=player, state="disabled", disabledforeground="black" if player == "X" else "red")
        winner = self.check_winner(self.board)
        if winner:
            messagebox.showinfo("Game Over", f"{winner} wins!" if winner != "Draw" else "It's a Draw!")

    def check_winner(self, b):
        win_states = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        for s in win_states:
            if b[s[0]] == b[s[1]] == b[s[2]] != "": return b[s[0]]
        if "" not in b: return "Draw"
        return None

    # --- THE MATH ---
    def minimax(self, board, depth, is_maximizing):
        res = self.check_winner(board)
        if res == self.ai: return 10 - depth
        if res == self.human: return depth - 10
        if res == "Draw": return 0

        if is_maximizing:
            best_score = -float('inf')
            for i in range(9):
                if board[i] == "":
                    board[i] = self.ai
                    score = self.minimax(board, depth + 1, False)
                    board[i] = ""
                    best_score = max(score, best_score)
            return best_score
        else:
            best_score = float('inf')
            for i in range(9):
                if board[i] == "":
                    board[i] = self.human
                    score = self.minimax(board, depth + 1, True)
                    board[i] = ""
                    best_score = min(score, best_score)
            return best_score

    def ai_move(self):
        best_score = -float('inf')
        move = None
        for i in range(9):
            if self.board[i] == "":
                self.board[i] = self.ai
                score = self.minimax(self.board, 0, False)
                self.board[i] = ""
                if score > best_score:
                    best_score = score
                    move = i
        if move is not None:
            self.make_move(move, self.ai)

    def reset(self):
        self.board = [""] * 9
        for btn in self.buttons:
            btn.config(text="", state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    game = TicTacToe(root)
    root.mainloop()