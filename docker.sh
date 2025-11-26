#!/usr/bin/env bash
set -euo pipefail

# docker.sh - build and run FunGame Docker image
# Usage: ./docker.sh [build|run|stop|logs|rm|rebuild|help]

IMAGE_NAME="fungame:latest"
CONTAINER_NAME="fungame_app"
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FRONTEND_DIR="$ROOT_DIR/frontend"
DOCKERFILE_PATH="$ROOT_DIR/Dockerfile"

print_help(){
  cat <<EOF
Usage: ./docker.sh <command>

Commands:
  build      Build the frontend (npm) then build the Docker image (${IMAGE_NAME})
  run        Run the container (detached) with port 5000 published
  stop       Stop the running container
  logs       Show container logs (follow)
  rm         Remove the stopped container
  rebuild    Stop, remove, build image again and run
  shell      Start a shell inside a new container (for debugging)
  help       Show this help

Notes:
- Dockerfile at project root is used. It performs a multi-stage build that builds the frontend then copies artifacts into the Python image.
- Ensure Docker is running and you have permission to run docker commands.
EOF
}

check_docker(){
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is not installed or not in PATH" >&2
    exit 2
  fi
}

build_frontend(){
  echo "Building frontend..."
  if [ ! -d "$FRONTEND_DIR" ]; then
    echo "Frontend directory not found: $FRONTEND_DIR" >&2
    exit 1
  fi
  pushd "$FRONTEND_DIR" >/dev/null
  if [ -f package-lock.json ]; then
    npm ci --silent
  else
    npm install --silent
  fi
  npm run build
  popd >/dev/null
}

docker_build(){
  check_docker
  if [ ! -f "$DOCKERFILE_PATH" ]; then
    echo "Dockerfile not found at $DOCKERFILE_PATH" >&2
    exit 1
  fi
  echo "Building Docker image ${IMAGE_NAME}..."
  docker build -t "$IMAGE_NAME" "$ROOT_DIR"
}

docker_run(){
  check_docker
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container ${CONTAINER_NAME} already exists. Stopping and removing..."
    docker rm -f "$CONTAINER_NAME" || true
  fi
  echo "Running container ${CONTAINER_NAME} (port 5000 -> 5000)..."
  docker run -d --name "$CONTAINER_NAME" -p 5000:5000 "$IMAGE_NAME"
  echo "Container started. Use './docker.sh logs' to follow logs."
}

docker_stop(){
  check_docker
  if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping ${CONTAINER_NAME}..."
    docker stop "$CONTAINER_NAME"
  else
    echo "No running container named ${CONTAINER_NAME}"
  fi
}

docker_logs(){
  check_docker
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker logs -f "${CONTAINER_NAME}"
  else
    echo "No container named ${CONTAINER_NAME}"
  fi
}

docker_rm(){
  check_docker
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker rm -f "${CONTAINER_NAME}"
    echo "Removed container ${CONTAINER_NAME}"
  else
    echo "No container named ${CONTAINER_NAME} to remove"
  fi
}

docker_shell(){
  check_docker
  docker run --rm -it --name "${CONTAINER_NAME}_debug" -p 5000:5000 "$IMAGE_NAME" /bin/bash
}

case ${1-""} in
  build)
    build_frontend
    docker_build
    ;;
  run)
    docker_run
    ;;
  stop)
    docker_stop
    ;;
  logs)
    docker_logs
    ;;
  rm)
    docker_rm
    ;;
  rebuild)
    docker_stop || true
    docker_rm || true
    build_frontend
    docker_build
    docker_run
    ;;
  shell)
    docker_shell
    ;;
  help|""|*)
    print_help
    ;;
esac
