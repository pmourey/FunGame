import threading
import time
import random
import math
from game.state import GameStore


class Bot:
    """Simple AI bot that can join a GameStore game and act on its turn.

    Behavior:
    - Joins a game via GameStore.add_player
    - If the game is in 'waiting' state, calls game.start() to roll initiative
    - When it's the bot's turn it will:
      - attempt to attack an adjacent alive player
      - otherwise move to a random adjacent free tile
      - then end its turn
    - Runs in a background thread with configurable think interval
    """

    def __init__(self, game_id, name='Computer', think_interval=1.0, color=None):
        self.game_id = game_id
        self.name = name
        self.think_interval = think_interval
        self.color = color
        self._stop = threading.Event()
        self._thread = None
        self.player_id = None

    def start(self):
        game = GameStore.get_game(self.game_id)
        if not game:
            raise RuntimeError(f"game {self.game_id} not found")
        # create and add player
        player = GameStore.add_player(self.game_id, self.name)
        if not player:
            raise RuntimeError(f"failed to add bot to game {self.game_id}")
        self.player_id = player.id
        # mark connected
        GameStore.set_player_connected(self.game_id, self.player_id, True)
        print(f"Bot {self.name} ({self.player_id}) added to game {self.game_id}")
        # if waiting, start the game (roll initiative)
        if game.status == 'waiting':
            try:
                game.start()
                print(f"Bot {self.player_id}: started game (rolled initiative). Queue={game.turn_queue}")
            except Exception as e:
                print(f"Bot {self.player_id}: failed to start game: {e}")
        else:
            # If game already running, roll initiative for this new entity and insert into turn_queue
            try:
                # roll initiative for the new player
                roll = random.randint(1, 20)
                player.initiative = roll
                # build entries from all existing entities (players + monsters)
                entries = []
                for p in list(game.players.values()) + list(game.monsters.values()):
                    # ensure initiative exists (default 0)
                    iv = getattr(p, 'initiative', 0) or 0
                    entries.append((iv, p.id))
                # sort by initiative desc
                entries.sort(reverse=True)
                new_queue = [eid for (_, eid) in entries]
                # preserve current_turn: rotate queue so previous current remains at head
                prev_current = game.current_turn
                if prev_current and prev_current in new_queue:
                    # rotate until head == prev_current
                    while new_queue and new_queue[0] != prev_current:
                        new_queue.append(new_queue.pop(0))
                game.turn_queue = new_queue
                game.current_turn = game.turn_queue[0] if game.turn_queue else None
                game.log.append({'event': 'initiative_add', 'entity': player.id, 'roll': roll, 'queue': game.turn_queue, 'time': time.time()})
                print(f"Bot {self.player_id}: assigned initiative {roll}, new queue={game.turn_queue}")
            except Exception as e:
                print(f"failed to assign initiative to bot {self.player_id} in game {self.game_id}: {e}")
        # launch background thread
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"Bot {self.player_id}: background thread started")
        return self.player_id

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run_loop(self):
        game = GameStore.get_game(self.game_id)
        if not game:
            return
        while not self._stop.is_set():
            try:
                # reload game reference each loop (store is in-memory)
                game = GameStore.get_game(self.game_id)
                if not game:
                    break
                # if game not running, just wait
                if game.status != 'running':
                    time.sleep(self.think_interval)
                    continue

                # --- sanitize turn queue: remove dead entities and ensure current_turn valid ---
                try:
                    # remove dead entities from turn_queue
                    alive_ids = set()
                    for p in list(game.players.values()) + list(game.monsters.values()):
                        if getattr(p, 'hp', 0) > 0:
                            alive_ids.add(p.id)
                    # filter queue
                    new_queue = [eid for eid in game.turn_queue if eid in alive_ids]
                    # if bot is alive and not present, keep it available
                    if getattr(game.players.get(self.player_id) or game.monsters.get(self.player_id), 'hp', 0) > 0:
                        if self.player_id not in new_queue:
                            new_queue.append(self.player_id)
                    game.turn_queue = new_queue
                    # ensure current_turn is valid
                    if not game.turn_queue:
                        game.current_turn = None
                    else:
                        if game.current_turn not in game.turn_queue:
                            # set to head or None
                            game.current_turn = game.turn_queue[0]
                except Exception as _:
                    pass

                # if there are no alive opponents (only bot alive or none), make sure bot can act
                bot_actor = game.players.get(self.player_id) or game.monsters.get(self.player_id)
                if bot_actor and getattr(bot_actor, 'hp', 0) > 0:
                    # count alive non-bot entities
                    alive_non_bot = [p for p in list(game.players.values()) + list(game.monsters.values()) if p.id != self.player_id and getattr(p, 'hp', 0) > 0]
                    if not alive_non_bot:
                        # ensure bot is in queue and set as current_turn so it can act
                        if self.player_id not in game.turn_queue:
                            game.turn_queue.append(self.player_id)
                        if game.current_turn != self.player_id:
                            game.current_turn = self.player_id

                # if bot is dead or removed, break
                bot_actor = game.players.get(self.player_id) or game.monsters.get(self.player_id)
                if not bot_actor:
                    break
                if getattr(bot_actor, 'hp', 0) <= 0:
                    # try to respawn
                    print(f"Bot {self.player_id}: dead, attempting respawn")
                    game.process_action(self.player_id, {'type': 'respawn'})
                    time.sleep(self.think_interval)
                    continue

                # If it's not bot's turn, wait
                if game.current_turn != self.player_id:
                    # debug log occasionally to trace
                    # print(f"Bot {self.player_id}: waiting, current_turn={game.current_turn}")
                    time.sleep(self.think_interval)
                    continue

                # It's the bot's turn -> choose action
                print(f"Bot {self.name}: it's my turn")
                acted = False
                # try to find adjacent player to attack
                bx = bot_actor.position.get('x', 0)
                by = bot_actor.position.get('y', 0)
                candidates = []
                for p in list(game.players.values()) + list(game.monsters.values()):
                    if p.id == self.player_id:
                        continue
                    if getattr(p, 'hp', 0) <= 0:
                        continue
                    dx = abs(p.position.get('x', 0) - bx)
                    dy = abs(p.position.get('y', 0) - by)
                    # adjacency: 4-directional
                    if (dx == 1 and dy == 0) or (dx == 0 and dy == 1):
                        candidates.append(p)
                if candidates:
                    target = random.choice(candidates)
                    print(f"Bot {self.name}: attacking target {target.id} at pos {target.position}")
                    res = game.process_action(self.player_id, {'type': 'attack', 'targetId': target.id})
                    acted = True
                    if isinstance(res, dict) and res.get('error'):
                        print(f"Bot {self.name}: attack error: {res}")
                    else:
                        print(f"Bot {self.name}: attack result: {res}")
                else:
                    # move to a random adjacent free tile within map
                    moves = [(0,1),(0,-1),(1,0),(-1,0)]
                    random.shuffle(moves)
                    moved = False
                    for dx, dy in moves:
                        nx = bx + dx
                        ny = by + dy
                        # bounds check if map exists
                        if game.map:
                            if ny < 0 or ny >= len(game.map) or nx < 0 or nx >= len(game.map[0]):
                                continue
                        # check occupancy
                        occupied = False
                        for p in list(game.players.values()) + list(game.monsters.values()):
                            if p.id == self.player_id:
                                continue
                            if getattr(p, 'hp', 1) <= 0:
                                continue
                            pos = p.position or {}
                            if pos.get('x') == nx and pos.get('y') == ny:
                                occupied = True
                                break
                        if occupied:
                            continue
                        # perform move
                        print(f"Bot {self.name}: moving to {nx},{ny}")
                        res = game.process_action(self.player_id, {'type': 'move', 'x': nx, 'y': ny})
                        moved = True
                        acted = True
                        if isinstance(res, dict) and res.get('error'):
                            print(f"Bot {self.name}: move error: {res}")
                        else:
                            print(f"Bot {self.name}: move result: {res}")
                        break
                # end turn if we acted (or even if not, to avoid stuck turns)
                # If the action already advanced the turn (result contains 'next'), do not call end_turn again.
                try:
                    need_end_turn = True
                    if 'res' in locals() and isinstance(res, dict) and res.get('next'):
                        need_end_turn = False
                    if acted:
                        print(f"Bot {self.name}: ending turn (acted={acted}, need_end_turn={need_end_turn})")
                        if need_end_turn:
                            game.process_action(self.player_id, {'type': 'end_turn'})
                    else:
                        # if we didn't act, advance to avoid stuck turns
                        print(f"Bot {self.name}: no action possible, advancing turn")
                        game.process_action(self.player_id, {'type': 'end_turn'})
                except Exception as e:
                    print(f"Bot {self.name}: error ending/advancing turn: {e}")
                # short sleep after action
                time.sleep(self.think_interval)
            except Exception as e:
                # log the error to stdout to help debug
                print(f"Bot error in game {self.game_id}: {e}")
                time.sleep(self.think_interval)
        # cleanup
        try:
            GameStore.set_player_connected(self.game_id, self.player_id, False)
        except Exception:
            pass
