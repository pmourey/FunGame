# Copilot / Agent Instructions for FunGame

Résumé rapide
- Backend: Flask app in `backend/` exposing a small REST API (`backend/api.py`) and Socket.IO handlers (`backend/socketio_events.py`). The app serves the built frontend from `frontend/dist` when present (`backend/app.py`).
- In-memory game storage: `backend/models.py` defines `GameState` and `GameStore` (thread-safe singleton map). Turn logic lives in `backend/game/engine.py`.
- Frontend: React + PixiJS in `frontend/src/App.jsx`. Uses `socket.io-client` for realtime updates and REST endpoints to create/join games.

Important files (start here)
- `backend/app.py` — app factory and Socket.IO startup; dev uses `async_mode='threading'` and `socketio.run(...)`.
- `backend/api.py` — REST endpoints: `POST /api/games` (create), `GET /api/games` (list), `POST /api/games/<id>/join` (join), `GET /api/games/<id>/state` (snapshot).
- `backend/socketio_events.py` — socket events: `connect`, `join`, `leave`, `start_game`, `action`, `disconnect`. Use this to change realtime contracts.
- `backend/models.py` — `GameState`, `Player`, `Monster`; `GameState.process_action()` is the canonical place for game rules.
- `backend/game/engine.py` — initiative and turn rotation logic (advance_turn, roll_initiative).
- `frontend/src/App.jsx` — client logic, PIXI rendering, grid constants (`TILE_SIZE`, grid dims), and socket event handlers.

Architecture & data flow (concise)
- Game lifecycle: REST -> create game -> add players (via `GameStore.add_player`) -> clients `join` via Socket.IO -> server broadcasts `state_update` and `action_result` events.
- State is authoritative on server. Clients render snapshots sent by `state_update` and send intent via `socket.emit('action', {...})`.
- In-memory store: `GameStore._games` is not persistent. Tests and local dev rely on this behavior — avoid assuming persistence.

Developer workflows
- Quick dev (recommended):
  ```bash
  ./start_dev.sh
  ```
  This script creates a `.venv`, installs `backend/requirements.txt`, installs frontend deps (if missing) and runs the frontend dev server (Vite) and backend (Flask+Socket.IO).
- Production build + run:
  ```bash
  ./start_prod.sh
  ```
  This builds the frontend into `frontend/dist` and then runs `python backend/app.py` which will serve static files.
- Backend tests: run pytest from repo root or inside `backend/`:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -r backend/requirements.txt
  pytest backend/tests
  ```
- Frontend dev/test:
  ```bash
  cd frontend
  npm install       # if needed
  npm run dev       # vite dev server
  npm run build     # production build
  npm test          # vitest
  ```

Project-specific conventions & gotchas
- Socket message shapes are minimal and must match both sides. Examples (from `App.jsx` / `socketio_events.py`):
  - Emit to join: `socket.emit('join', { gameId, playerId })`
  - Server sends state: `socket.on('state_update', state)`
  - Client action: `socket.emit('action', { gameId, playerId, action: { type: 'move', x, y } })`
- Server uses a simple `_session_map` to map websocket sid -> (gameId, playerId). `disconnect` handlers rely on that; preserve the format when changing connection logic.
- `GameStore` operations are protected by a threading lock; changes to game lifecycle should respect `GameStore._lock` or the class methods.
- Map/grid constants: server generates a 16x12 grid (`backend/models.py`) and the frontend uses the same dimensions/constants in `App.jsx`. If you change grid size, update both sides.
- The frontend stores `gameId` and `playerId` in `sessionStorage` and attempts rejoin on socket `connect`. If you change join semantics, ensure rejoin flow still works.

When to modify which files
- Gameplay rules and action resolution: `backend/models.py` (GameState.process_action) and `backend/game/engine.py` for turn ordering.
- Realtime API surface: `backend/socketio_events.py` (add/remove events, change payloads) AND `frontend/src/App.jsx` (update listeners/emits accordingly).
- REST endpoints for tooling/admin: `backend/api.py`.

Testing & verification tips
- Use `pytest backend/tests` after changing server logic. Tests exist for API, engine and models.
- Run `./start_dev.sh` to get a quick dev environment that runs both frontend and backend together (useful to verify socket flows and PIXI rendering).

Examples (curl / socket)
- Create game (REST):
  ```bash
  curl -X POST -H "Content-Type: application/json" -d '{"name":"New","maxPlayers":4}' http://localhost:5000/api/games
  ```
- Join (REST):
  ```bash
  curl -X POST -H "Content-Type: application/json" -d '{"playerName":"Bob"}' http://localhost:5000/api/games/<gameId>/join
  ```
- Socket (client):
  ```js
  socket.emit('join', { gameId: '...', playerId: '...' })
  socket.emit('action', { gameId: '...', playerId: '...', action: { type: 'move', x: 5, y: 3 } })
  ```

Notes for the agent
- Preserve API payload shapes unless you update both server and client.
- Favor small, atomic changes: adjust `GameState.process_action` and add tests in `backend/tests/` for each rule change.
- Avoid introducing persistence assumptions — this project is intentionally in-memory.
- If you change grid/viewport sizes, update both `backend/models.py` and `frontend/src/App.jsx` constants (`16x12`, `TILE_SIZE`).

Questions / Missing info
- Should we add CI steps (tests/build) or a GitHub Action workflow? If yes, tell me preferred test matrix (python/node versions) and I can scaffold a minimal workflow.

---
Merci — dites-moi si vous voulez que j'ajoute des exemples supplémentaires ou que je génère une action GitHub CI pour tests/build.
