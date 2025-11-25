import threading
import uuid
import time
from models import GameState, Player, COLORS
import random


class GameStore:
    _games = {}
    _lock = threading.Lock()

    @classmethod
    def create_game(cls, name='Game', max_players=2):
        with cls._lock:
            # create a new independent game for each call (tests expect this)
            game = GameState(name=name, max_players=max_players)
            cls._games[game.id] = game
            return game

    @classmethod
    def list_games(cls):
        with cls._lock:
            return list(cls._games.values())

    @classmethod
    def get_game(cls, game_id):
        with cls._lock:
            return cls._games.get(game_id)

    @classmethod
    def get_player(cls, game_id, player_id):
        game = cls.get_game(game_id)
        if game:
            return game.get_player(player_id)
        return None

    @classmethod
    def set_player_connected(cls, game_id, player_id, connected):
        game = cls.get_game(game_id)
        if game:
            game.set_player_connected(player_id, connected)

    @classmethod
    def add_player(cls, game_id, player_name):
        game = cls.get_game(game_id)
        if not game:
            return None
        # choose a color not already taken
        used = [p.color for p in game.players.values() if getattr(p, 'color', None) is not None]
        color = None
        for c in COLORS:
            if c not in used:
                color = c
                break
        if color is None:
            # fallback: pick random color from palette
            color = random.choice(COLORS)
        player = Player(name=player_name, color=color)
        success = game.add_player(player)
        if success:
            return player
        return None



# ... potential cleanup utilities
