import random
import time

class Engine:
    """Simple turn engine: computes initiative and advances turns."""

    def __init__(self, game_state):
        self.game_state = game_state

    def roll_initiative(self):
        # compute initiative for all entities (players + monsters)
        entries = []
        for p in list(self.game_state.players.values()) + list(self.game_state.monsters.values()):
            # d20 roll
            roll = random.randint(1, 20)
            # store initiative value on entity
            p.initiative = roll
            entries.append((roll, p.id))
        # sort by initiative desc, tie-break by insertion order
        entries.sort(reverse=True)
        # store as queue of ids
        self.game_state.turn_queue = [eid for (_, eid) in entries]
        self.game_state.current_turn = self.game_state.turn_queue[0] if self.game_state.turn_queue else None
        self.game_state.log.append({'event': 'initiative_roll', 'queue': self.game_state.turn_queue, 'time': time.time()})

    def advance_turn(self):
        """Rotate to next entity in the queue."""
        if not self.game_state.turn_queue:
            self.game_state.current_turn = None
            return None
        # pop first and append to end
        first = self.game_state.turn_queue.pop(0)
        self.game_state.turn_queue.append(first)
        self.game_state.current_turn = self.game_state.turn_queue[0]
        self.game_state.log.append({'event': 'advance_turn', 'current': self.game_state.current_turn, 'time': time.time()})
        return self.game_state.current_turn

    def remove_entity(self, entity_id):
        # remove from queue if present
        if entity_id in self.game_state.turn_queue:
            self.game_state.turn_queue = [e for e in self.game_state.turn_queue if e != entity_id]
            if self.game_state.current_turn == entity_id:
                # advance if removed current
                self.advance_turn()

    # placeholder for more engine features (timeouts, AP refresh, etc.)
