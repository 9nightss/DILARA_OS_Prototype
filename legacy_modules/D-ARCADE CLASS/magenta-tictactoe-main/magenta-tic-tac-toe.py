from itertools import cycle
win_conditions = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
optimal_moves = [4, 0, 2, 6, 8, 1, 3, 5, 7]
def check_win(board):
    for line in win_conditions:
        if board[line[0]] == board[line[1]] == board[line[2]] != ' ':
            return board[line[0]]
    if ' ' not in board:
        return 'D'
    return None
def find_move(board, player):
    for move in optimal_moves:
        if board[move] == ' ':
            test_board = list(board)
            test_board[move] = player
            if check_win(test_board) == player:
                return move
    for move in optimal_moves:
        if board[move] == ' ':
            test_board = list(board)
            test_board[move] = 'X' if player == 'O' else 'O'
            if check_win(test_board) == ('X' if player == 'O' else 'O'):
                return move
    for move in optimal_moves:
        if board[move] == ' ':
            return move
def draw_board(board):
    print("\n 1 | 2 | 3      {} | {} | {}".format(*board[:3]))
    print("---+---+---    ---+---+---")
    print(" 4 | 5 | 6      {} | {} | {}".format(*board[3:6]))
    print("---+---+---    ---+---+---")
    print(" 7 | 8 | 9      {} | {} | {}".format(*board[6:]))
def game():
    while True:
        board = [' '] * 9
        for player in cycle('OX'):
            draw_board(board)
            if player == 'O':
                move = find_move(list(board), player)
            else:
                move = int(input("Your move (1-9): ")) - 1
                while move not in range(9) or board[move] != ' ':
                    move = int(input("Invalid move. Please try again: ")) - 1
            board[move] = player
            win = check_win(board)
            if win:
                draw_board(board)
                if win == 'D':
                    print("Game over. Draw! The only winning move is not to play.")
                else:
                    print("Game over. {} wins! The only winning move for you is not to play.".format(player))
                break
        play_again = input("Do you want to play again? (yes/no): ")
        if play_again.lower() != "y":
            break
if __name__ == "__main__":
    game()