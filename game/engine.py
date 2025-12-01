import random
import time

class Engine:
    """Simple turn engine: computes initiative and advances turns."""

    def __init__(self, game_state):
        self.game_state = game_state

    def _name_for(self, entity_id):
        # helper to get a readable name for an id
        g = self.game_state
        ent = g.players.get(entity_id) or g.monsters.get(entity_id)
        return getattr(ent, 'name', entity_id) if ent is not None else entity_id

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
        queue_ids = [eid for (_, eid) in entries]
        self.game_state.turn_queue = queue_ids
        self.game_state.current_turn = self.game_state.turn_queue[0] if self.game_state.turn_queue else None
        # build readable queue names for logging
        queue_names = [self._name_for(eid) for eid in queue_ids]
        self.game_state.log.append({'event': 'initiative_roll', 'queue_ids': queue_ids, 'queue_names': queue_names, 'time': time.time()})

    def advance_turn(self):
        """Rotate to next entity in the queue."""
        if not self.game_state.turn_queue:
            self.game_state.current_turn = None
            return None
        # pop first and append to end
        first = self.game_state.turn_queue.pop(0)
        self.game_state.turn_queue.append(first)
        self.game_state.current_turn = self.game_state.turn_queue[0]
        # include readable name for current turn
        current_name = self._name_for(self.game_state.current_turn)
        self.game_state.log.append({'event': 'advance_turn', 'current': self.game_state.current_turn, 'current_name': current_name, 'time': time.time()})
        return self.game_state.current_turn

    def remove_entity(self, entity_id):
        # remove from queue if present
        if entity_id in self.game_state.turn_queue:
            self.game_state.turn_queue = [e for e in self.game_state.turn_queue if e != entity_id]
            if self.game_state.current_turn == entity_id:
                # advance if removed current
                self.advance_turn()

    # placeholder for more engine features (timeouts, AP refresh, etc.)
