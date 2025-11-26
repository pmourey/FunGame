# FunGame Frontend

Intégration PixiJS via @inlet/react-pixi (Option B).

Pré-requis:
- Node 18+ (ou compatible)

Installation:

```bash
cd frontend
npm install
```

Démarrer le serveur de développement:

```bash
npm run dev
```

Notes:
- Le frontend se connecte par défaut au backend Socket.IO à `http://localhost:5000`.
- Le rendu PixiJS utilise des textures générées dynamiquement (rectangles colorés). Remplacez par des sprites réels dans `src/App.jsx` si nécessaire.
- Les actions utilisateur (clic sur la grille) émettent un événement `move` au backend avec payload {gameId, playerId, x, y}.

