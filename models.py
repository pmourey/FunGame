import uuid
import random
import time
from game.engine import Engine
import math
import socketio_instance as _si

# Mapping d'erreurs => messages lisibles (français)
ERROR_MESSAGES = {
    'actor_not_found': "Acteur introuvable",
    'actor_dead': "L'acteur est mort",
    'occupied': "La case est occupée",
    'target_not_found': "Cible introuvable",
    'target_dead': "La cible est déjà morte",
    'not_your_turn': "Ce n'est pas votre tour",
    'not_dead': "L'acteur n'est pas mort",
    'unknown_action': "Action inconnue",
}


def _err(code):
    return {'error': code, 'message': ERROR_MESSAGES.get(code, code)}


def _new_id():
    return uuid.uuid4().hex


# Simple random name generator
ADJECTIVES = [
    'Brave', 'Mighty', 'Swift', 'Clever', 'Fierce', 'Nimble', 'Bold', 'Silent', 'Lucky', 'Wise'
]
NOUNS = [
    'Fox', 'Wolf', 'Hawk', 'Bear', 'Lion', 'Raven', 'Tiger', 'Otter', 'Eagle', 'Stag'
]

def random_name():
    return f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)}"


# Palette of colors (integers) to assign to players. Pick in order, avoid duplicates.
COLORS = [
    0x00ff00,  # green
    0x0000ff,  # blue
    0xff0000,  # red
    0xffff00,  # yellow
    0xff00ff,  # magenta
    0x00ffff,  # cyan
    0x8888ff,  # light purple
    0xff8800,  # orange
]


class Player:
    def __init__(self, name='Player', color=None):
        self.id = _new_id()
        # if no explicit name provided, generate a friendly random name
        if not name:
            self.name = random_name()
        else:
            self.name = name
        self.hp = 10
        self.max_hp = 10
        self.ac = 10
        self.position = {'x': 0, 'y': 0}
        self.initiative = 0
        # default to not connected; Socket join will mark connected=True
        self.is_connected = False
        self.color = color
        # gameplay score (number of kills)
        self.score = 0

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'hp': self.hp,
            'max_hp': self.max_hp,
            'ac': self.ac,
            'position': self.position,
            'initiative': self.initiative,
            'is_connected': self.is_connected,
            'color': self.color,
            'score': self.score,
        }


class Monster(Player):
    def __init__(self, template_id='goblin'):
        super().__init__(name=template_id)
        self.template_id = template_id


class GameState:
    def __init__(self, name='Game', max_players=2):
        self.id = _new_id()
        self.name = name
        self.max_players = max_players
        self.players = {}
        self.monsters = {}
        self.map = None
        self.turn_queue = []
        self.current_turn = None
        self.status = 'waiting'  # waiting, running, finished
        self.log = []
        self.created_at = time.time()
        # engine instance
        self.engine = Engine(self)

    def add_player(self, player):
        if len(self.players) >= self.max_players:
            return False
        # add player to registry first
        self.players[player.id] = player

        # choose spawn: try corners first, then any free tile on map if available
        corners = [(0, 0), (15, 0), (0, 11), (15, 11)]

        def is_occupied(x, y):
            for p in list(self.players.values()) + list(self.monsters.values()):
                if p.id == player.id:
                    continue
                pos = p.position or {}
                if pos.get('x') == x and pos.get('y') == y:
                    return True
            return False

        for cx, cy in corners:
            if not is_occupied(cx, cy):
                player.position = {'x': cx, 'y': cy}
                break
        else:
            # if map exists, scan for first non-occupied tile
            if self.map:
                found = False
                for y in range(len(self.map)):
                    for x in range(len(self.map[0])):
                        if not is_occupied(x, y):
                            player.position = {'x': x, 'y': y}
                            found = True
                            break
                    if found:
                        break
                if not found:
                    # fallback
                    player.position = {'x': 0, 'y': 0}
            else:
                player.position = {'x': 0, 'y': 0}

        return True

    def get_player(self, player_id):
        return self.players.get(player_id)

    def set_player_connected(self, player_id, connected=True):
        p = self.players.get(player_id)
        if p:
            p.is_connected = connected

    def start(self):
        # use engine to roll initiative
        self.engine.roll_initiative()
        self.status = 'running'
        self.log.append({'event': 'game_started', 'time': time.time()})
        # generate a simple map: 16x12 grid, all floor (0)
        self.map = [[0 for _ in range(16)] for _ in range(12)]

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'players': [p.to_dict() for p in self.players.values()],
            'monsters': [m.to_dict() for m in self.monsters.values()],
            'turn_queue': self.turn_queue,
            'current_turn': self.current_turn,
            'log': self.log,
            'map': self.map,
        }

    def process_action(self, player_id, action):
        # Action processor: move / attack / end_turn / respawn
        actor = self.players.get(player_id) or self.monsters.get(player_id)
        if not actor:
            return _err('actor_not_found')
        # allow 'respawn'/'revive' actions even if actor is dead; otherwise dead actors cannot act
        typ = action.get('type')
        # Enforce turn order: if a turn queue exists (or current_turn is set), only the entity whose id matches
        # current_turn may perform actions (except respawn/revive which are allowed anytime)
        if typ not in ('respawn', 'revive') and (self.current_turn is not None or self.turn_queue):
            if actor.id != self.current_turn:
                return _err('not_your_turn')
        if getattr(actor, 'hp', 0) <= 0 and typ not in ('respawn', 'revive'):
            return _err('actor_dead')
        if typ == 'move':
            x = int(action.get('x', actor.position['x']))
            y = int(action.get('y', actor.position['y']))
            # don't allow moving onto occupied tile (alive entities)
            occupied = any((p.position.get('x') == x and p.position.get('y') == y) for p in list(self.players.values()) + list(self.monsters.values()) if p.id != actor.id and getattr(p, 'hp', 1) > 0)
            if occupied:
                return _err('occupied')
            actor.position = {'x': x, 'y': y}
            # log with readable name and id
            self.log.append({'event': 'move', 'actor': actor.name, 'actor_id': actor.id, 'pos': actor.position, 'time': time.time()})
            res = {'ok': True, 'action': 'move', 'pos': actor.position, 'message': f"Déplacé en {actor.position['x']},{actor.position['y']}"}
            # advance the turn after a move so player cannot both move and attack in same turn
            try:
                next_entity = self.engine.advance_turn()
                res['next'] = next_entity
            except Exception:
                pass
            # server-side emit via socketio if available
            try:
                if _si and hasattr(_si, 'emit_event'):
                    _si.emit_event('action_result', res, to=self.id)
                    _si.emit_event('state_update', self.to_dict(), to=self.id)
            except Exception:
                pass
            return res

        elif typ == 'attack':
            target_id = action.get('targetId')
            target = self.players.get(target_id) or self.monsters.get(target_id)
            if not target:
                return _err('target_not_found')
            # cannot attack dead targets
            if getattr(target, 'hp', 1) <= 0:
                return _err('target_dead')
            # perform attack roll (1-20) and damage (1-6) on hit
            dx = actor.position.get('x', 0) - target.position.get('x', 0)
            dy = actor.position.get('y', 0) - target.position.get('y', 0)
            dist = math.sqrt(dx*dx + dy*dy)
            roll = random.randint(1, 20)
            hit = (roll >= getattr(target, 'ac', 10))
            dmg = 0
            if hit:
                dmg = random.randint(1, 6)
                target.hp -= dmg
            # log attack with readable names and ids
            self.log.append({'event': 'attack', 'actor': actor.name, 'actor_id': actor.id, 'target': target.name, 'target_id': target.id, 'dist': dist, 'roll': roll, 'hit': hit, 'dmg': dmg, 'time': time.time()})
            died = False
            if hit and target.hp <= 0:
                target.hp = 0
                died = True
                # remove from turn queue if needed
                try:
                    self.engine.remove_entity(target.id)
                except Exception:
                    pass
                # log death with readable name
                self.log.append({'event': 'death', 'entity': target.name, 'entity_id': target.id, 'time': time.time()})
                # If a player killed another player, increment the killer's score
                try:
                    if target_id in self.players and actor.id in self.players:
                        killer = self.players.get(actor.id)
                        killer.score = getattr(killer, 'score', 0) + 1
                        # log the kill event with names
                        self.log.append({'event': 'kill', 'killer': actor.name, 'killer_id': actor.id, 'victim': target.name, 'victim_id': target.id, 'time': time.time()})
                except Exception:
                    pass
            msg = f"Attaque {'réussie' if hit else 'manquée'}"
            if hit:
                msg += f" - dégâts: {dmg}"
            res = {'ok': True, 'action': 'attack', 'target': target_id, 'dmg': dmg, 'died': died, 'hit': hit, 'roll': roll, 'message': msg}
            # auto-advance turn after attack so opponents (including bots) get chance to act
            try:
                next_entity = self.engine.advance_turn()
                res['next'] = next_entity
            except Exception:
                pass
            # emit via socketio if available
            try:
                if _si and hasattr(_si, 'emit_event'):
                    _si.emit_event('action_result', res, to=self.id)
                    _si.emit_event('state_update', self.to_dict(), to=self.id)
            except Exception:
                pass
            return res

        elif typ == 'respawn' or typ == 'revive':
            # revive the actor if dead
            if getattr(actor, 'hp', 1) > 0:
                return _err('not_dead')
            actor.hp = getattr(actor, 'max_hp', 10)
            # place on free tile
            def is_occupied(x, y):
                for p in list(self.players.values()) + list(self.monsters.values()):
                    if p.id == actor.id:
                        continue
                    pos = p.position or {}
                    if pos.get('x') == x and pos.get('y') == y and getattr(p, 'hp', 1) > 0:
                        return True
                return False

            corners = [(0, 0), (15, 0), (0, 11), (15, 11)]
            for cx, cy in corners:
                if not is_occupied(cx, cy):
                    actor.position = {'x': cx, 'y': cy}
                    break
            else:
                if self.map:
                    placed = False
                    for y in range(len(self.map)):
                        for x in range(len(self.map[0])):
                            if not is_occupied(x, y):
                                actor.position = {'x': x, 'y': y}
                                placed = True
                                break
                        if placed:
                            break
                    if not placed:
                        actor.position = {'x': 0, 'y': 0}
                else:
                    actor.position = {'x': 0, 'y': 0}
            self.log.append({'event': 'respawn', 'player': actor.name, 'player_id': actor.id, 'time': time.time()})
            # ensure actor is in turn queue so they become active again
            try:
                if actor.id not in self.turn_queue:
                    self.turn_queue.append(actor.id)
                    if not self.current_turn:
                        self.current_turn = actor.id
            except Exception:
                pass
            return {'ok': True, 'action': 'respawn', 'pos': actor.position, 'message': 'Réapparu'}

        elif typ == 'end_turn':
            next_entity = self.engine.advance_turn()
            return {'ok': True, 'action': 'end_turn', 'next': next_entity}

        else:
            return _err('unknown_action')
