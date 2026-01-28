"""Tic-Tac-Toe (XO) game module for Friday assistant."""

import tkinter as tk
from tkinter import messagebox
import random
from typing import Optional, Callable


class XOGame:
    """
    Tic-Tac-Toe game window where the user plays against Friday (AI).
    
    - User is 'X', Friday is 'O'
    - Friday makes moves automatically after user's turn
    - Score tracking persists across games
    - Voice interaction remains active during gameplay
    """
    
    def __init__(self, voice_engine, on_game_end: Optional[Callable] = None, command_processor=None):
        """
        Initialize the XO game.
        
        Args:
            voice_engine: VoiceEngine instance for Friday to speak
            on_game_end: Optional callback when game window closes (for score reporting)
            command_processor: Optional CommandProcessor to enable conversation mode
        """
        self.voice_engine = voice_engine
        self.on_game_end = on_game_end
        self.command_processor = command_processor
        
        # Score tracking
        self.user_wins = 0
        self.friday_wins = 0
        self.draws = 0
        
        # Game state
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'  # User starts
        self.game_over = False

        # Light-weight small talk content - casual and chill
        self.chill_questions = [
            "Uhm, while we play, tell me bro, how was your day?",
            "Dude, if you could travel anywhere after this, where would you go?",
            "Man, do you prefer strategy games or action games?",
            "Uhm, what music do you listen to while coding, bro?",
            "Hey, what's your favorite programming language, dude?",
            "Bro, tell me something cool you learned recently.",
        ]
        self.jokes = [
            "Uhm, why do programmers prefer dark mode, bro? Because light attracts bugs.",
            "Dude, I tried to write a joke about UDP, but you might not get it.",
            "Man, why did the developer go broke? Because he used up all his cache.",
            "Uhm, I'm not saying I'm always right, but I am compiled without errors, bro.",
            "Bro, why don't programmers like nature? It has too many bugs.",
        ]
        
        # Create game window
        self.root = tk.Toplevel()
        self.root.title("FRIDAY // Tic-Tac-Toe")
        self.root.geometry("450x550")
        self.root.configure(bg="#050816")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self._setup_ui()
        import random
        greetings = [
            "Uhm, let's play Tic-Tac-Toe, bro. You're X, I'm O. You go first!",
            "Alright dude, Tic-Tac-Toe time! You're X, I'm O. Your move, man.",
            "Hey bro, let's do this! Tic-Tac-Toe. You're X, I'm O. Go ahead.",
        ]
        self.voice_engine.speak(random.choice(greetings))
    
    def _setup_ui(self):
        """Build the game UI."""
        # Title
        title_label = tk.Label(
            self.root,
            text="TIC-TAC-TOE",
            font=('Consolas', 18, 'bold'),
            bg='#050816',
            fg='#00d9ff'
        )
        title_label.pack(pady=10)
        
        # Score display
        score_frame = tk.Frame(self.root, bg="#050816")
        score_frame.pack(pady=5)
        
        self.score_label = tk.Label(
            score_frame,
            text=f"You: {self.user_wins} | Friday: {self.friday_wins} | Draws: {self.draws}",
            font=('Consolas', 10),
            bg='#050816',
            fg='#00ffae'
        )
        self.score_label.pack()
        
        # Turn indicator
        self.turn_label = tk.Label(
            self.root,
            text="Your turn (X)",
            font=('Consolas', 11, 'bold'),
            bg='#050816',
            fg='#00e676'
        )
        self.turn_label.pack(pady=5)
        
        # Game board (3x3 grid)
        board_frame = tk.Frame(self.root, bg="#050816")
        board_frame.pack(pady=20)
        
        self.buttons = []
        for i in range(3):
            row = []
            for j in range(3):
                btn = tk.Button(
                    board_frame,
                    text='',
                    font=('Consolas', 24, 'bold'),
                    width=4,
                    height=2,
                    bg='#000814',
                    fg='#e0f7fa',
                    activebackground='#1b2735',
                    activeforeground='#00e5ff',
                    relief=tk.FLAT,
                    command=lambda r=i, c=j: self.on_cell_click(r, c)
                )
                btn.grid(row=i, column=j, padx=2, pady=2)
                row.append(btn)
            self.buttons.append(row)
        
        # Control buttons
        control_frame = tk.Frame(self.root, bg="#050816")
        control_frame.pack(pady=10)
        
        reset_btn = tk.Button(
            control_frame,
            text="NEW GAME",
            font=('Consolas', 10, 'bold'),
            bg='#2962ff',
            fg='#e3f2fd',
            relief=tk.FLAT,
            command=self.reset_game
        )
        reset_btn.pack(side=tk.LEFT, padx=5)
        
        close_btn = tk.Button(
            control_frame,
            text="CLOSE",
            font=('Consolas', 10, 'bold'),
            bg='#ff1744',
            fg='#ffffff',
            relief=tk.FLAT,
            command=self.on_close
        )
        close_btn.pack(side=tk.LEFT, padx=5)
    
    def on_cell_click(self, row: int, col: int):
        """Handle user clicking a cell."""
        if self.game_over or self.current_player != 'X' or self.board[row][col] != '':
            return
        
        # User's move
        self.board[row][col] = 'X'
        self.buttons[row][col].config(text='X', fg='#00e676', state=tk.DISABLED)

        # Light banter after a few moves
        self._maybe_chit_chat()
        
        # Check for win or draw
        if self._check_winner('X'):
            self.game_over = True
            self.user_wins += 1
            self._update_score()
            import random
            responses = [
                "Uhm, congrats bro! You won!",
                "Dude, nice! You got me!",
                "Man, good game! You won!",
                "Bro, you're good at this!",
            ]
            self.voice_engine.speak(random.choice(responses))
            self.turn_label.config(text="You won!", fg='#00e676')
            self._disable_all_buttons()
            return
        
        if self._is_board_full():
            self.game_over = True
            self.draws += 1
            self._update_score()
            import random
            responses = [
                "Uhm, it's a draw, bro! Good game.",
                "Dude, we tied! Good one, man.",
                "Bro, draw! That was fun.",
            ]
            self.voice_engine.speak(random.choice(responses))
            self.turn_label.config(text="Draw!", fg='#ffa726')
            return
        
        # Friday's turn
        self.current_player = 'O'
        self.turn_label.config(text="Friday's turn (O)", fg='#00d9ff')
        self.root.update()
        
        # Friday makes a move (AI)
        self.root.after(500, self.friday_move)  # Small delay for better UX
    
    def friday_move(self):
        """Friday (AI) makes a move."""
        if self.game_over:
            return
        
        # Simple AI: try to win, then block, then random
        move = self._find_winning_move('O')
        if move is None:
            move = self._find_winning_move('X')  # Block user
        if move is None:
            move = self._find_random_move()
        
        if move:
            row, col = move
            self.board[row][col] = 'O'
            self.buttons[row][col].config(text='O', fg='#00d9ff', state=tk.DISABLED)
            
            if self._check_winner('O'):
                self.game_over = True
                self.friday_wins += 1
                self._update_score()
                import random
                responses = [
                    "Uhm, I won, bro! Better luck next time, dude.",
                    "Dude, I got you this time!",
                    "Man, I won! Good game though, bro.",
                ]
                self.voice_engine.speak(random.choice(responses))
                self.turn_label.config(text="Friday won!", fg='#00d9ff')
                self._disable_all_buttons()
                return
            
            if self._is_board_full():
                self.game_over = True
                self.draws += 1
                self._update_score()
                import random
                responses = [
                    "Uhm, it's a draw, bro! Good game.",
                    "Dude, we tied! Good one, man.",
                    "Bro, draw! That was fun.",
                ]
                self.voice_engine.speak(random.choice(responses))
                self.turn_label.config(text="Draw!", fg='#ffa726')
                return
            
            # Back to user's turn
            self.current_player = 'X'
            self.turn_label.config(text="Your turn (X)", fg='#00e676')

            # Occasionally drop a quick comment on Friday's move
            self._maybe_comment_on_move()
    
    def _find_winning_move(self, player: str) -> Optional[tuple]:
        """Find a winning move for the given player."""
        for i in range(3):
            for j in range(3):
                if self.board[i][j] == '':
                    self.board[i][j] = player
                    if self._check_winner(player):
                        self.board[i][j] = ''
                        return (i, j)
                    self.board[i][j] = ''
        return None
    
    def _find_random_move(self) -> Optional[tuple]:
        """Find a random available move."""
        available = [(i, j) for i in range(3) for j in range(3) if self.board[i][j] == '']
        return random.choice(available) if available else None
    
    def _check_winner(self, player: str) -> bool:
        """Check if the given player has won."""
        # Rows
        for i in range(3):
            if all(self.board[i][j] == player for j in range(3)):
                return True
        # Columns
        for j in range(3):
            if all(self.board[i][j] == player for i in range(3)):
                return True
        # Diagonals
        if all(self.board[i][i] == player for i in range(3)):
            return True
        if all(self.board[i][2-i] == player for i in range(3)):
            return True
        return False
    
    def _is_board_full(self) -> bool:
        """Check if the board is full."""
        return all(self.board[i][j] != '' for i in range(3) for j in range(3))
    
    def _disable_all_buttons(self):
        """Disable all buttons when game ends."""
        for row in self.buttons:
            for btn in row:
                btn.config(state=tk.DISABLED)
    
    def _update_score(self):
        """Update the score display."""
        self.score_label.config(
            text=f"You: {self.user_wins} | Friday: {self.friday_wins} | Draws: {self.draws}"
        )

    def _maybe_chit_chat(self):
        """Randomly ask a chill question or tell a quick joke while you play."""
        # ~25% chance to speak, keep it non‑intrusive
        if random.random() > 0.25:
            return
        # 50/50 between joke and question
        if random.random() < 0.5 and self.jokes:
            line = random.choice(self.jokes)
            is_question = False
        else:
            line = random.choice(self.chill_questions)
            is_question = True
        
        # Enable conversation mode if asking a question
        if is_question and self.command_processor:
            self.command_processor.conversation_mode = True
            # Auto-disable after 10 seconds
            import threading
            def disable_conv_mode():
                import time
                time.sleep(10)
                if self.command_processor:
                    self.command_processor.conversation_mode = False
            threading.Thread(target=disable_conv_mode, daemon=True).start()
        
        try:
            self.voice_engine.speak(line)
        except Exception:
            pass

    def _maybe_comment_on_move(self):
        """Short, game‑flavoured comments from Friday - casual and chill."""
        lines = [
            "Uhm, interesting move, bro. Let's see where that goes.",
            "Dude, bold choice. I like your style.",
            "Man, I'm calculating my next move carefully.",
            "Bro, you're making this game fun.",
            "Uhm, nice move, dude.",
            "Alright, let me think about this, man.",
            "Cool move, bro.",
        ]
        if random.random() > 0.2:
            return
        try:
            self.voice_engine.speak(random.choice(lines))
        except Exception:
            pass
    
    def reset_game(self):
        """Start a new game."""
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
        self.game_over = False
        
        for i in range(3):
            for j in range(3):
                self.buttons[i][j].config(text='', state=tk.NORMAL)
        
        self.turn_label.config(text="Your turn (X)", fg='#00e676')
        import random
        responses = [
            "Uhm, new game, bro! Your turn.",
            "Alright dude, new game! Go ahead, man.",
            "Bro, new game! Your move.",
        ]
        self.voice_engine.speak(random.choice(responses))
    
    def on_close(self):
        """Handle window close event."""
        if self.on_game_end:
            score_msg = (
                f"Final score: You won {self.user_wins}, "
                f"I won {self.friday_wins}, "
                f"and we had {self.draws} draws."
            )
            self.on_game_end(self.user_wins, self.friday_wins, self.draws)
        self.root.destroy()
