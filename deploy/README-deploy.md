# Déploiement FunGame (nginx sur port 6000)

Ce document décrit comment démarrer le stack de production localement avec nginx qui termine le TLS et expose le site sur le port 6000 (https://philippe.mourey.com:6000).

Résumé des scripts fournis:
- `docker-compose.yml` : définit deux services `fungame` (Flask) et `nginx` (reverse-proxy TLS) ; nginx écoute sur le port 6000.
- `scripts/deploy_https.sh` : script pour builder, démarrer `fungame` + `nginx`, attendre la santé et tester la préflight PNA (Private Network Access).
- `start_prod.sh` : starter minimal qui démarre uniquement le service `fungame` (utile si vous ne voulez pas nginx).

Prérequis
- Docker Engine + Docker Compose (v2) installés.
- Certificats TLS pour `philippe.mourey.com` disponibles dans `deploy/certs/philippe.pem` et `deploy/certs/philippe-key.pem` (voir section "Créer des certificats" ci-dessous).
- Le hostname `philippe.mourey.com` résolu vers l'IP publique de votre box/NAT si vous testez depuis l'extérieur.

Démarrage complet (nginx TLS -> port 6000)

1. Placer vos certificats (PEM / key) dans `deploy/certs/`.
2. Lancer le script de déploiement HTTPS :

```bash
./scripts/deploy_https.sh
```

Le script : build l'image `fungame`, démarre `fungame` puis `nginx`, attend l'endpoint `/api` via HTTPS et exécute une requête OPTIONS pour vérifier la préflight PNA.

Démarrage minimal (sans nginx)

```bash
./start_prod.sh
```

Ce script démarre seulement le container `fungame` et teste rapidement `http://localhost:5000/api`.

Vérifications manuelles

- API health via nginx HTTPS :

```bash
curl -k -v https://philippe.mourey.com:6000/api
```

- Préflight PNA (OPTIONS) :

```bash
curl -k -i -X OPTIONS "https://philippe.mourey.com:6000/socket.io/?EIO=4&transport=polling" \
  -H "Origin: http://philippe.mourey.com:6000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: content-type" \
  -H "Access-Control-Request-Private-Network: true"
```

Note importante sur Private Network Access (PNA)
- Les navigateurs modernes rejettent les requêtes fetch/xhr vers `localhost` depuis une page servie via `http` non sécurisé. Pour que la préflight PNA fonctionne, la page d'origine doit être servie via HTTPS et l'en-tête `Access-Control-Request-Private-Network: true` doit être accepté côté serveur/proxy.
- C'est pourquoi on termine le TLS sur nginx et on proxifie vers la Flask interne.

Créer des certificats (mkcert)
- macOS / Linux (recommandé pour dev local) :
  1. Installer mkcert (Homebrew sur macOS): `brew install mkcert nss` puis `mkcert -install`.
  2. Générer un certificat pour `philippe.mourey.com` :
     ```bash
     mkcert philippe.mourey.com
     ```
     Ceci crée deux fichiers `philippe.mourey.com.pem` et `philippe.mourey.com-key.pem`. Renommez-les en `philippe.pem` et `philippe-key.pem` et placez-les dans `deploy/certs/`.

- Windows 10 (avec Chocolatey) :
  1. Installer Chocolatey (si non installé) : ouvrir PowerShell en administrateur et exécuter :
     ```powershell
     Set-ExecutionPolicy Bypass -Scope Process -Force; \
     [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; \
     iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
     ```
  2. Installer mkcert via choco :
     ```powershell
     choco install mkcert -y
     mkcert -install
     mkcert philippe.mourey.com
     ```
  3. Récupérer les deux fichiers PEM générés, renommez-les et copiez-les dans `deploy/certs/` sur votre machine de déploiement.

Les certificats mkcert générés sur macOS sont généralement valides sur Windows si la machine qui fait confiance à la CA est la même (ou si vous importez la CA racine mkcert sur la machine Windows). Dans un environnement distribué, il est plus simple de générer/installer mkcert localement sur chaque machine cliente ou d'utiliser une CA partagée.

Conseils et résolution de problèmes
- Si vous avez des erreurs CORS / PNA : vérifiez que le header `Access-Control-Allow-Origin` renvoyé par nginx correspond à l'origine du navigateur (ex: `https://philippe.mourey.com:6000`) et que la directive `Access-Control-Allow-Private-Network` est configurée si nécessaire.
- Logs :
  - Voir logs nginx : `docker compose logs -f nginx`
  - Voir logs backend : `docker compose logs -f fungame`
- Pour redémarrer proprement :

```bash
# teardown
docker compose down --remove-orphans
# rebuild & start
./scripts/deploy_https.sh
```

Tests
- Les tests unitaires côté backend se lancent avec :

```bash
pytest -q
```

---

Si vous voulez, j'ajoute une configuration nginx plus stricte d'en-têtes CORS/PNA et un exemple de `nginx.conf` avec `add_header` pour `Access-Control-Allow-Private-Network`.

