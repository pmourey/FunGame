Development README for FunGame backend

To run the backend server (development):

1. Create virtualenv and activate

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run server

```bash
python app.py
```

The server will start on port 5000 and support Socket.IO connections.

Quick REST smoke tests

Create a game:

```bash
curl -X POST http://localhost:5000/api/games -H "Content-Type: application/json" -d '{"name":"QuickGame","maxPlayers":2}'
```

Join a game (replace <gameId>):

```bash
curl -X POST http://localhost:5000/api/games/<gameId>/join -H "Content-Type: application/json" -d '{"playerName":"Alice"}'
```

Get game state:

```bash
curl http://localhost:5000/api/games/<gameId>/state
```

Quick Socket.IO test (node):

Create a quick `test-socket.js`:

```js
const io = require('socket.io-client');
const socket = io('http://localhost:5000');

socket.on('connect', () => {
  console.log('connected', socket.id);
  socket.emit('join', { gameId: '<gameId>', playerId: '<playerId>' });
});

socket.on('joined', data => console.log('joined', data));
socket.on('state_update', s => console.log('state:', s));
```

Run:

```bash
node test-socket.js
```

Notes
- The server currently stores game state in memory (GameStore). For production or multi-process scaling use Redis and Flask-SocketIO message_queue.
- The server is authoritative: clients submit 'action' events and receive 'state_update' broadcasts.
