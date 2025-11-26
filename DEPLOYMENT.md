# Déploiement - FunGame

Ce document décrit comment construire et déployer FunGame en production à l'aide de Docker et docker-compose, ainsi que des conseils de debug (ports, NAT/Freebox, healthchecks) et des solutions de contournement rapides (ngrok).

Prérequis
- Docker (Engine) et docker-compose installés sur l'hôte.
- Node/npm pour builder localement le frontend si vous ne voulez pas laisser Docker le faire.
- (Optionnel) Un nom de domaine et une redirection NAT/port correctement configurée sur votre routeur.

Rappels importants
- L'application attend le build frontend dans `frontend/dist` (Flask sert ces fichiers). Le Dockerfile multi-stage construit le frontend et copie `frontend/dist` dans l'image finale.
- L'application écoute sur le port 5000. Le healthcheck Docker pointe `/api`.

Commandes utiles
- Construire l'image Docker (depuis la racine du repo) :

```bash
docker build --no-cache -t fungame:latest .
```

- Lancer avec docker-compose (recréation complète) :

```bash
docker-compose up -d --build
# suivre les logs
docker-compose logs -f
```

- Lancer un conteneur de test local :

```bash
# supprimez l'ancien conteneur si besoin
docker rm -f fungame_test || true
# run avec mapping du port 5000
docker run -d --name fungame_test -p 5000:5000 fungame:latest
# tester l'API depuis l'hôte
curl -i http://localhost:5000/api
```

Démarrage sans Docker (script `start_prod.sh`)
- Le script `start_prod.sh` construit le frontend (si `frontend/` existe), crée/active une venv, installe les dépendances Python et lance `app.py`.

```bash
# depuis la racine du repo
./start_prod.sh
```

Debug & vérification (si problèmes d'accès depuis l'extérieur)
1) Vérifier que le service est accessible localement :

```bash
curl -i http://localhost:5000/api
curl -i http://<LAN_IP>:5000/api   # remplacer <LAN_IP> par l'IP locale de la machine (ex: 192.168.1.187)
```

2) Si accessible en LAN mais pas depuis WAN (ERR_CONNECTION_REFUSED) :
- Vérifier la règle de redirection (NAT / port forwarding) sur votre routeur / Freebox : port externe (ex: 60000) → IP interne `192.168.x.y` port 5000, protocole TCP.
- Vérifier que l'IP WAN affichée par la Freebox correspond à votre IP publique (pas de CGNAT). Si votre FAI utilise CGNAT, vous ne pourrez pas ouvrir de port sans une IP publique.
- Test depuis l'extérieur (mobile 4G ou autre réseau) :

```bash
curl -i http://<votre_domaine_ou_ip_publique>:<port_externe>/api
```

3) Commandes de diagnostic utiles :

```bash
# vérifier containers et ports
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
# inspecter le mapping des ports
docker inspect --format='{{json .NetworkSettings.Ports}}' <container_name> | python3 -m json.tool
# logs
docker logs --tail 200 <container_name>
```

Contournement rapide avec ngrok (si vous n'avez pas d'IP publique)
- Installez ngrok et exposez le port local 5000 :

```bash
# installer/ngrok login auparavant
ngrok http 5000
# ensuite utilisez l'URL publique fournie par ngrok, p.ex. https://abcd1234.ngrok.io/api
```

Conseils de production
- Utiliser un reverse proxy (nginx, Caddy) pour gérer TLS et domaines, puis proxy_pass vers le conteneur (localhost:5000). Exemple minimal : mettre NGINX en frontal et faire proxy vers `http://fungame:5000` si vous déployez via compose avec un réseau.
- Ne pas exposer directement le port 5000 sur internet sans TLS/proxy; préférez une couche reverse proxy.
- Automatiser la construction et déploiement via CI (GitHub Actions) : build image, push vers registry, puis déploiement ou rollouts.

Notes spécifiques Freebox / NAT
- Sur certaines box (Freebox), il existe la gestion du service « redirection de ports » et la réservation DHCP (réserver l'IP interne à la machine pour éviter le changement d'IP). Après création de la redirection, redémarrez la box pour vous assurer que la règle est active.
- Si la Freebox indique une IP WAN privée (ex: 10.x.x.x ou 100.64.x.x) alors vous êtes derrière du CGNAT — solution : demande d'IP publique auprès du FAI ou tunneling (ngrok, SSH reverse tunnel vers un serveur public).

Sécurité et nettoyage
- Exclure `node_modules`, `frontend/dist`, `.venv`, fichiers compilés et secrets du contexte Docker si non nécessaires via `.dockerignore`.
- Ne stockez pas de secrets non chiffrés dans l'image. Utilisez variables d'environnement ou secret managers.

Annexes : commandes rapides

```bash
# reconstruire l'image et lancer (local)
docker build -t fungame:latest .
docker run -p 5000:5000 fungame:latest

# vérifier la présence du build frontend à l'intérieur du conteneur
docker run --rm fungame:latest ls -la /app/frontend/dist
```

Si vous voulez, je peux :
- ajouter un service `nginx` dans `docker-compose.yml` pour TLS et reverse proxy, ou
- générer un `docker-compose.prod.yml` avec un reverse-proxy et des volumes prêts pour production.

---
Version: générée automatiquement le 26/11/2025.

