# Makefile minimal
# target: start-prod -> builds and starts the production stack

.PHONY: start-prod stop logs ps build clean clean-images prune deploy-https

start-prod:
	./start_prod.sh

stop:
	docker compose down

logs:
	docker compose logs -f fungame

ps:
	docker compose ps

build:
	docker compose build fungame

# Safe cleanup: stop the compose stack and remove volumes/orphans
clean:
	docker compose down --volumes --remove-orphans

# Remove the local fungame image if you want (non-destructive by default)
clean-images:
	docker rmi fungame:latest || true

# Prune unused Docker objects (use with care)
prune:
	docker system prune --volumes -f

# Deploy with HTTPS reverse-proxy (requires mkcert certificates in deploy/certs)
deploy-https:
	./scripts/deploy_https.sh
