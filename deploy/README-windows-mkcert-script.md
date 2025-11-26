# Guide d'utilisation du script Windows mkcert

Ce document décrit comment utiliser le script PowerShell `scripts/windows_mkcert_setup.ps1` fourni dans ce dépôt pour automatiser l'installation de mkcert, la génération des certificats locaux (pour `philippe.mourey.com` et `philippe.mourey.com:60000`), l'ajout optionnel d'une entrée hosts et le lancement optionnel du déploiement Docker (backend + nginx).

> IMPORTANT : exécutez toutes les commandes PowerShell en tant qu'administrateur (Run as Administrator).

## Objectif

Le script automatise :
- la détection / installation de `mkcert` (via Chocolatey si disponible ou en téléchargeant le binaire),
- l'exécution de `mkcert -install` pour ajouter une CA locale digne de confiance,
- la génération des certificats TLS pour `philippe.mourey.com` et `philippe.mourey.com:60000`,
- la copie/renommage des fichiers PEM dans `deploy/certs/philippe.pem` et `deploy/certs/philippe-key.pem`,
- une option interactive pour ajouter l'entrée `127.0.0.1 philippe.mourey.com` au fichier hosts Windows,
- une option interactive pour lancer immédiatement le déploiement Docker (build + up pour `fungame` et `nginx`).

## Prérequis

- Windows 10 (PowerShell) avec droits Administrateur.
- Docker Desktop installé et démarré si vous souhaitez lancer le déploiement automatiquement.
- (Optionnel) Chocolatey si vous voulez installer `mkcert` via choco — le script gère l'absence de Chocolatey en téléchargeant le binaire.

## Emplacement du script

Le script se trouve ici :

```
scripts/windows_mkcert_setup.ps1
```

## Étapes d'utilisation (pas-à-pas)

1. Ouvrir PowerShell en mode Administrateur (Run as Administrator).
2. Se placer dans la racine du dépôt :

```powershell
cd C:\Path\To\FunGame
```

3. Lancer le script (en tant qu'Administrateur) :

```powershell
.\scripts\windows_mkcert_setup.ps1
```

4. Suivre les invites interactives :
   - Le script peut proposer d'ajouter l'entrée hosts `127.0.0.1 philippe.mourey.com` — répondre `Y` pour accepter.
   - À la fin, le script propose de lancer immédiatement le déploiement Docker (build + up). Répondez `Y` pour lancer automatiquement les commandes Docker (si `docker compose` est disponible dans votre environnement).

## Que fait exactement le script

- Vérifie qu'il est exécuté avec des privilèges Administrateur.
- Si `mkcert` est présent sur le PATH, il l'utilise ; sinon, si Chocolatey (`choco`) est présent, il installe `mkcert` via `choco install mkcert -y`.
- Si `mkcert` n'est pas disponible et que `choco` n'est pas installé ou l'installation échoue, le script télécharge le binaire `mkcert.exe` depuis la release GitHub la plus récente.
- Exécute `mkcert -install` pour ajouter la CA locale.
- Génère les certificats pour `philippe.mourey.com` et `philippe.mourey.com:60000` dans le dossier `deploy`.
- Recherche les fichiers PEM générés, choisit les plus récents, et les copie dans `deploy/certs/` sous les noms `philippe.pem` et `philippe-key.pem`.
- Tente de durcir les permissions des fichiers avec `icacls` (opération non bloquante si elle échoue).
- Propose d'ajouter l'entrée dans le fichier hosts Windows (vérifie d'abord si l'entrée existe déjà).
- Propose d'exécuter les commandes Docker suivantes :
  - `docker compose build fungame`
  - `docker compose up -d fungame`
  - `docker compose up -d nginx`

Si vous refusez l'étape de déploiement, le script termine et vous pouvez lancer manuellement `make deploy-https` ou les commandes Docker précédentes.

## Emplacement des certificats produits

Après exécution, les certificats doivent se trouver dans :

```
deploy/certs/philippe.pem
deploy/certs/philippe-key.pem
```

## Test rapide après génération

- Vérifier le contenu du dossier :

```powershell
Get-ChildItem -Path .\deploy\certs
```

- Vérifier l'API via nginx HTTPS (si vous avez démarré le proxy) :

```powershell
# si la CA mkcert est installée et reconnue
curl -i https://philippe.mourey.com:60000/api

# en mode dev (ignorer la vérification TLS)
curl -k -i https://philippe.mourey.com:60000/api
```

- Tester la préflight PNA (doit renvoyer `Access-Control-Allow-Private-Network: true` si origin autorisée) :

```powershell
curl -k -i -X OPTIONS "https://philippe.mourey.com:60000/socket.io/?EIO=4&transport=polling" `
  -H "Origin: http://philippe.mourey.com:60000" `
  -H "Access-Control-Request-Method: GET" `
  -H "Access-Control-Request-Headers: content-type" `
  -H "Access-Control-Request-Private-Network: true"
```

## Dépannage courant

- `This script must be run as Administrator` : relancez PowerShell en mode Administrateur.
- `choco` non installé : le script téléchargera `mkcert.exe`; vous pouvez aussi installer manuellement Chocolatey puis relancer le script.
- `mkcert -install` échoue : vérifiez que PowerShell est en Admin et que votre antivirus ne bloque pas l'ajout de CA.
- `docker compose` introuvable : installez Docker Desktop et démarrez‑le avant d'accepter le déploiement automatisé.
- Port 60000 déjà utilisé : adaptez `deploy/nginx.conf` et `docker-compose.override.yml` si nécessaire, puis redémarrez.

## Options supplémentaires

Si vous souhaitez :
- exécuter le déploiement sans invite interactive, dites‑le et je peux ajouter un paramètre `-AutoDeploy` au script;
- supprimer la CA locale mkcert après tests (undo), je peux fournir un script de désinstallation.

---

_Fichier généré automatiquement : `deploy/README-windows-mkcert-script.md` — instructions en français pour automatiser mkcert sous Windows et lancer le proxy HTTPS local._

