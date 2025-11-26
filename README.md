# FunGame — Démarrage production simplifié

Ce dépôt contient une petite application Flask + Socket.IO (frontend en React/Pixi). Cette version fournit une configuration simplifiée pour démarrer le backend directement (sans `nginx`) en production locale.

Fichiers importants
- `docker-compose.yml` — compose minimal exposant le service `fungame` sur le port 5000.
- `start_prod.sh` — script de démarrage simple pour builder (optionnel) et démarrer `fungame`.
- `Makefile` — cibles pratiques : `make start-prod`, `make stop`, `make logs`, `make ps`, `make build`.
- `tools/run_client.py` — client Python de test Socket.IO (optionnel).

Démarrage rapide (local)
1) Assurez-vous que Docker est installé et fonctionnel.

2) Démarrage (recommandé - rebuild) :

```bash
# depuis la racine du projet
./start_prod.sh
# ou via Makefile
make start-prod
```

3) Démarrage rapide sans rebuild (utile si l'image a déjà été construite) :

```bash
NO_BUILD=1 ./start_prod.sh
```

4) Vérifier que l'API répond :

```bash
curl -i http://localhost:5000/api
```

Tests et debug
- Suivre les logs :

```bash
docker compose logs -f fungame
```

- Créer une partie (exemple) :

```bash
curl -X POST -H "Content-Type: application/json" -d '{"name":"Test","maxPlayers":4}' http://localhost:5000/api/games
```

- Rejoindre via REST (remplacer `<gameId>`) :

```bash
curl -X POST -H "Content-Type: application/json" -d '{}' http://localhost:5000/api/games/<gameId>/join
```

- Test Socket.IO (client Python) :
  - Installer : `python3 -m pip install --user python-socketio websocket-client`
  - Utiliser `tools/run_client.py` (ou le snippet fourni dans la documentation).

Notes production
- Pour une vraie mise en production, réintroduire un reverse-proxy (nginx/Caddy/Traefik) pour TLS, header hardening et static caching.
- Si vous scalez en plusieurs instances, ajoutez un backend pub/sub (Redis) pour Socket.IO (message broker) afin de synchroniser les sockets entre instances.

Besoin d'aide ?
- Si vous voulez que je pousse une configuration `nginx` prête pour la prod (TLS + WebSocket), je peux la générer.
- Si vous préférez que je crée un workflow GitHub Actions pour build + tests, dites-le et je le configure.

---
README généré automatiquement — instructions en français pour un démarrage local rapide.

