Local HTTPS with mkcert and Nginx (philippe.mourey.com)

This short guide shows how to generate local trusted certificates using `mkcert`, place them into `deploy/certs` and run the local nginx reverse-proxy (on port 60000) to terminate TLS and proxy to the `fungame` service on port 5000.

1) Install mkcert

macOS (Homebrew):

```bash
brew install mkcert
brew install nss # optional, for firefox
mkcert -install
```

Windows 10 (Chocolatey or manual):

- Option A — with Chocolatey (recommended if you have Chocolatey installed):

```powershell
choco install mkcert -y
# then open an elevated PowerShell (Run as Administrator) and run:
mkcert -install
```

- Option B — manual download (no package manager):

1. Visit the mkcert releases page: https://github.com/FiloSottile/mkcert/releases
2. Download the Windows binary (file name like `mkcert-vX.Y.Z-windows-amd64.exe`) into a folder on your PATH or the `deploy/` folder.
3. Rename it to `mkcert.exe` and (from an elevated PowerShell) run:

```powershell
.\\mkcert.exe -install
```

Notes for Windows:
- Run `mkcert -install` from an elevated prompt (Administrator). This installs a local CA in the Windows certificate store and attempts to make Firefox trust it when possible.
- If Firefox still complains, install the `nss-tools` / `certutil` variant for Windows or import the generated root CA manually into Firefox.

2) Generate certs for your domain(s)

macOS / Windows (same commands from the `deploy` folder):

```bash
cd deploy
mkcert philippe.mourey.com "philippe.mourey.com:60000"
```

mkcert will create two files (names may include suffixes like `+2`). Rename them to the expected names used by nginx in this repo:

```bash
# adjust filenames if mkcert appended suffixes (example names)
mv philippe.mourey.com+2.pem philippe.pem || true
mv philippe.mourey.com+2-key.pem philippe-key.pem || true
chmod 640 philippe.pem philippe-key.pem || true
```

On Windows use PowerShell to rename:
```powershell
Rename-Item -Path "philippe.mourey.com+2.pem" -NewName "philippe.pem"
Rename-Item -Path "philippe.mourey.com+2-key.pem" -NewName "philippe-key.pem"
```

3) Ensure hosts file includes the domain pointing to localhost

- macOS / Linux (as before): edit `/etc/hosts` and add:

```
127.0.0.1 philippe.mourey.com
```

- Windows 10: open Notepad as Administrator and edit `C:\Windows\System32\drivers\etc\hosts`, add the same line:

```
127.0.0.1 philippe.mourey.com
```

Or run in an elevated PowerShell:

```powershell
Add-Content -Path "$env:windir\System32\drivers\etc\hosts" -Value "127.0.0.1 philippe.mourey.com"
```

4) Start services (same as before)

From project root:

```bash
# build and start fungame (backend)
docker compose build fungame
docker compose up -d fungame

# start nginx reverse-proxy defined in docker-compose.override.yml
docker compose up -d nginx
```

Or use the provided script:

```bash
make deploy-https
# or
./scripts/deploy_https.sh
```

5) Test

Open https://philippe.mourey.com:60000 in your browser (should be trusted by mkcert). The nginx reverse-proxy will forward requests to the fungame backend on port 5000 and properly handle websocket upgrades on /socket.io/.

Troubleshooting / tips
- Host resolution from LAN: if you're testing from another device on the LAN, ensure `philippe.mourey.com` resolves to the server's LAN IP (hairpin NAT is unreliable); editing the remote machine's `hosts` file to map the domain to the server's LAN IP is the simplest approach.
- Windows permissions: many mkcert steps require elevated privileges (Administrator). If you get permission errors, re-run the command prompt / PowerShell as Administrator.
- If Firefox doesn't trust the mkcert root automatically on Windows, import the generated root CA manually into Firefox's certificate manager.
- For production use real certificates (Let's Encrypt, etc.) and a proper reverse-proxy.

Notes
- mkcert is intended for local development only. It creates a local CA and installs trust locally — don't use the generated CA in production.
- The `deploy/certs` folder is mounted into the nginx container by `docker-compose.override.yml` so nginx can read the TLS certs.

If you want, I can also add a short Windows PowerShell script to automate the mkcert download + install + cert generation and placement into `deploy/certs` (it would require Administrator privileges). Let me know if you want that and I will create it.
