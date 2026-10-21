This project is one of the games from the side branch of project DILARA called: D-Arcade

This engine evaluates the board state using a sum of three core logic systems:

    Material Weighting: Each piece is assigned a value (Pawn = 100, Queen = 900, etc.). The AI seeks to maximize its own material while minimizing yours.

    Piece-Square Tables (PST): 8x8 matrices provide "positional bonuses."

        Knights get bonuses for being in the center.

        Kings get bonuses for being tucked safely in corners (Castling).

        Pawns get stronger as they approach promotion.

    Minimax with Alpha-Beta Pruning: The AI simulates every possible move up to Depth 3. Alpha-Beta pruning allows the math to "cut off" branches that it knows are bad, making the calculation 10× faster.

New Features in this Update

    Castling: Fully implemented Kingside and Queenside castling with safety checks (the King cannot castle through check).

    Pawn Promotion: Interactive UI for players to choose their piece, while the AI mathematically defaults to the Queen.

    AI Visual Thought Process: Before moving, the AI highlights its Top 5 Candidate Moves in a purple color gradient, allowing you to see what it is considering.

    Checkmate/Stalemate Detection: Robust endgame logic that detects when no legal moves remain.

    Sound Triggers: Auditory feedback for every piece movement.

How to Run

    Ensure you have Python 3.x and Pillow installed:
    Bash

Known Issues

    En Passant: The current version does not support the "En Passant" pawn capture rule.

    Threefold Repetition: The game does not automatically declare a draw if the same position is reached three times.

    Performance: At Depth 4+, the calculation time increases significantly due to Python's single-threaded nature. Depth 3 is the recommended "sweet spot" for speed.

    Sound Latency: On some systems, winsound may cause a slight delay in the AI's visual highlights.

Future Roadmap

    [ ] Move History Log: A side panel showing PGN notation (e.g., 1. e4 e5 2. Nf3...).

    [ ] Depth Selector: A slider to change AI difficulty from "Easy" (Depth 1) to "Grandmaster" (Depth 5).

    [ ] Opening Book: Pre-programmed standard openings (like the Ruy Lopez) to make the AI faster in the early game.

    [ ] Timer: Integrated Blitz Chess clocks for both players.

    [ ] Networking: Option to play against a friend over a local network.
