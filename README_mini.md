Description du projet 
----------------------

Fonctionnalités
- Jeu multi‑joueurs en mémoire (Flask + Socket.IO).
- Grille fixe de 16x12, entités : joueurs et monstres.
- Tour par tour avec initiative et IA côté serveur.
- Actions supportées : `move`, `attack`, `end_turn`, `respawn/revive`.
- Realtime : événements `state_update` et `action_result` envoyés aux clients.

Architecture / pattern de code
- Backend :
  - `backend/models.py` : modèles en mémoire et logique de jeu (GameState, Player, Monster).
  - `backend/game/engine.py` : logique d'initiative et rotation des tours.
  - `backend/socketio_events.py` : pont Socket.IO (join/leave/action...).
  - REST pour création/join et snapshot (`backend/api.py`).
- Frontend :
  - React + PixiJS (rendu), `socket.io-client` pour les mises à jour.
  - Le client reçoit `state_update` et envoie `action` (shape minimale à préserver).
- Conventions :
  - Le serveur est source de vérité : le frontend se contente d'afficher l'état reçu.
  - Les payloads contiennent toujours `message` lisible pour simplifier le front.
  - Changez simultanément serveur et client si vous modifiez le shape des événements.

Développement rapide
- Lancer l'environnement dev :
  - `./start_dev.sh`
- Tests backend :
  - `pytest backend/tests`
