from flask import Blueprint, request, jsonify

from game.state import GameStore
from models import random_name
# Bot support
from game.bot import Bot

api_bp = Blueprint('api', __name__)


@api_bp.route('', methods=['GET'])
@api_bp.route('/', methods=['GET'])
def api_index():
    """Root of the API (mounted at /api). Returns minimal info so healthchecks can succeed."""
    return jsonify({
        'status': 'ok',
        'api_prefix': '/api',
        'endpoints': [
            '/api/games [GET,POST]',
            '/api/games/<game_id>/join [POST]',
            '/api/games/<game_id>/state [GET]'
        ]
    }), 200


@api_bp.route('/games', methods=['POST'])
def create_game():
    data = request.get_json() or {}
    name = data.get('name', 'Game')
    max_players = int(data.get('maxPlayers', 2))

    game = GameStore.create_game(name=name, max_players=max_players)
    # start the game if it hasn't been started yet (generate map, roll initiative)
    if getattr(game, 'status', None) == 'waiting' and not getattr(game, 'map', None):
        game.start()
    return jsonify({'gameId': game.id, 'name': game.name}), 201


@api_bp.route('/games', methods=['GET'])
def list_games():
    games = GameStore.list_games()
    return jsonify([{'gameId': g.id, 'name': g.name, 'status': g.status} for g in games])


@api_bp.route('/games/<game_id>/join', methods=['POST'])
def join_game(game_id):
    data = request.get_json() or {}
    player_name = data.get('playerName') or random_name()
    # option to auto-create/start a bot after join (default True for convenience)
    auto_bot = bool(data.get('autoBot', True))

    player = GameStore.add_player(game_id, player_name)
    if not player:
        return jsonify({'error': 'game not found or full'}), 404

    # get game object for response and checks
    game = GameStore.get_game(game_id)

    # attempt to add a single bot if requested and bot support is available
    if auto_bot and Bot is not None and game is not None:
        try:
            # avoid duplicate bots (detect by name prefix)
            has_bot = any((p.name or '').startswith('Computer') for p in game.players.values())
            # ensure there's room for the bot
            if not has_bot and len(game.players) < game.max_players:
                bot = Bot(game_id, name='Computer')
                try:
                    bot_id = bot.start()
                    # log successful bot start for visibility
                    print(f"started bot {bot_id} in game {game_id}")
                    # keep bot reference on game for potential future management
                    if not hasattr(game, '_bots'):
                        game._bots = []
                    game._bots.append(bot)
                except Exception as e:
                    print(f"failed to start bot for game {game_id}: {e}")
        except Exception:
            pass

    return jsonify({'playerId': player.id, 'name': player.name, **(game.to_dict() if game else {})}), 200


@api_bp.route('/games/<game_id>/state', methods=['GET'])
def get_state(game_id):
    game = GameStore.get_game(game_id)
    if not game:
        return jsonify({'error': 'not found'}), 404
    return jsonify(game.to_dict())
