from flask import Blueprint, request, jsonify
import uuid

from game.state import GameStore
from models import random_name

api_bp = Blueprint('api', __name__)


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
    player = GameStore.add_player(game_id, player_name)
    if not player:
        return jsonify({'error': 'game not found or full'}), 404
    return jsonify({'playerId': player.id, 'name': player.name}), 200


@api_bp.route('/games/<game_id>/state', methods=['GET'])
def get_state(game_id):
    game = GameStore.get_game(game_id)
    if not game:
        return jsonify({'error': 'not found'}), 404
    return jsonify(game.to_dict())
