from flask_socketio import emit, join_room, leave_room
from flask import request

# support both package-relative and top-level imports
from game.state import GameStore


# mapping of websocket session id to (game_id, player_id)
_session_map = {}


def register_socketio_handlers(socketio):

    @socketio.on('connect')
    def on_connect():
        sid = getattr(request, 'sid', None)
        addr = getattr(request, 'remote_addr', None)
        print(f'client connected sid={sid} remote_addr={addr}')
        emit('connected', {'msg': 'connected', 'sid': sid, 'remote_addr': addr})

    @socketio.on('join')
    def on_join(data, ack=None):
        # expected data: { gameId, playerId }
        data = data or {}
        game_id = data.get('gameId')
        player_id = data.get('playerId')
        if not game_id or not player_id:
            emit('error', {'message': 'gameId and playerId required'})
            if callable(ack):
                try: ack({'error': 'gameId and playerId required'})
                except Exception: pass
            return
        game = GameStore.get_game(game_id)
        if not game:
            emit('error', {'message': 'game not found'})
            if callable(ack):
                try: ack({'error': 'game not found'})
                except Exception: pass
            return
        # join socket.io room
        # prevent multiple simultaneous connections for the same player id
        try:
            player_obj = game.players.get(player_id)
        except Exception:
            player_obj = None
        if player_obj and getattr(player_obj, 'is_connected', False):
            emit('error', {'message': 'player already connected'})
            if callable(ack):
                try: ack({'error': 'player already connected'})
                except Exception: pass
            return
        # join socket.io room
        join_room(game_id)
        # mark player connected in game state
        game.set_player_connected(player_id, True)
        # store mapping for disconnect handling
        sid = getattr(request, 'sid', None)
        remote = getattr(request, 'remote_addr', None)
        if sid:
            _session_map[sid] = (game_id, player_id)
        # verbose log
        print(f"Player {player_id} connected via socket to game {game_id} (sid={sid}, remote_addr={remote})")
        # send 'joined' only to the joining client (include player's name so client can display it immediately)
        try:
            player_obj = game.players.get(player_id)
            player_name = player_obj.name if player_obj else None
        except Exception:
            player_name = None
        if sid:
            emit('joined', {'gameId': game_id, 'playerId': player_id, 'name': player_name}, to=sid)
        else:
            emit('joined', {'gameId': game_id, 'playerId': player_id, 'name': player_name})
        # send initial state update to all in the room
        print(f"emitting state_update to game {game_id} players")
        emit('state_update', game.to_dict(), to=game_id)
        # ack success to caller if they provided a callback
        if callable(ack):
            try:
                ack({'ok': True})
            except Exception:
                pass

    @socketio.on('start_game')
    def on_start(data):
        data = data or {}
        game_id = data.get('gameId')
        if not game_id:
            emit('error', {'message': 'gameId required'})
            return
        game = GameStore.get_game(game_id)
        if not game:
            emit('error', {'message': 'game not found'})
            return
        if game.status != 'waiting':
            emit('error', {'message': 'game already started or finished'})
            return
        game.start()
        print(f"game {game_id} started, broadcasting")
        emit('game_started', game.to_dict(), to=game_id)

    @socketio.on('action')
    def on_action(data):
        data = data or {}
        game_id = data.get('gameId')
        player_id = data.get('playerId')
        action = data.get('action') or {}
        if not game_id or not player_id:
            emit('error', {'message': 'gameId and playerId required'})
            return
        game = GameStore.get_game(game_id)
        if not game:
            emit('error', {'message': 'game not found'})
            return
        # simple authorization: ensure player exists in game
        if player_id not in game.players:
            emit('error', {'message': 'player not in game'})
            return
        result = game.process_action(player_id, action)
        # If result indicates error, send it only to the caller and don't broadcast
        sid = getattr(request, 'sid', None)
        if isinstance(result, dict) and result.get('error'):
            # map internal error codes to client-visible messages if desired
            err_code = result.get('error')
            # prefer a human-readable message if present
            msg = {'error': err_code, 'message': result.get('message') or result.get('error')}
            try:
                if sid:
                    emit('action_error', msg, to=sid)
                else:
                    emit('action_error', msg)
            except Exception:
                try:
                    emit('error', msg)
                except Exception:
                    pass
            # do not broadcast state in case of client error
            print(f"rejected action from {player_id} in game {game_id}: {result}")
            return
        # broadcast action result and full state snapshot
        print(f"action by {player_id} in game {game_id}: {action}, result: {result}")
        # action_result/state_update emitted from GameState.process_action; do not duplicate here
        # still emit an acknowledgement to the caller if desired
        try:
            if sid:
                emit('action_ack', {'ok': True}, to=sid)
        except Exception:
            pass

    @socketio.on('disconnect')
    def on_disconnect():
        sid = getattr(request, 'sid', None)
        remote = getattr(request, 'remote_addr', None)
        print(f'client disconnected sid={sid} remote_addr={remote}')
        mapping = _session_map.pop(sid, None)
        if mapping:
            # be robust: mapping might not be a 2-tuple in edge cases
            game_id = None
            player_id = None
            if isinstance(mapping, (list, tuple)) and len(mapping) == 2:
                game_id, player_id = mapping
            elif isinstance(mapping, dict):
                game_id = mapping.get('gameId') or mapping.get('game_id')
                player_id = mapping.get('playerId') or mapping.get('player_id')
            else:
                # unknown format: skip
                print('warning: unexpected session mapping format', mapping)
            if game_id and player_id:
                game = GameStore.get_game(game_id)
                if game:
                    game.set_player_connected(player_id, False)
                    emit('player_disconnected', {'playerId': player_id}, to=game_id)

    # optional: allow explicit leave
    @socketio.on('leave')
    def on_leave(data):
        data = data or {}
        game_id = data.get('gameId')
        player_id = data.get('playerId')
        if not game_id or not player_id:
            emit('error', {'message': 'gameId and playerId required'})
            return
        leave_room(game_id)
        sid = getattr(request, 'sid', None)
        if sid and sid in _session_map:
            _session_map.pop(sid, None)
        game = GameStore.get_game(game_id)
        if game:
            game.set_player_connected(player_id, False)
            emit('player_left', {'playerId': player_id}, to=game_id)
