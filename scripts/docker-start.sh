#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="k-container"
IMAGE_NAME="kapybara-basic-os:latest"
SSH_HOST_PORT=2222
COMPOSE_FILE="docker/docker-compose.env.yaml"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <workspace_path>" >&2
  echo "example: $0 \"${PWD}\"" >&2
  exit 1
fi

workspace_path="$1"
if [[ "${workspace_path}" != /* ]]; then
  workspace_path="${PWD}/${workspace_path}"
fi

if [[ ! -d "${workspace_path}" ]]; then
  echo "error: workspace path does not exist or is not a directory: ${workspace_path}" >&2
  exit 1
fi

HOST_WORKSPACE="$(cd -- "${workspace_path}" && pwd -P)"

PUID="$(id -u)"
PGID="$(id -g)"

export HOST_WORKSPACE
export CONTAINER_NAME
export IMAGE_NAME
export SSH_HOST_PORT
export PUID
export PGID

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

docker compose -f "${REPO_ROOT}/${COMPOSE_FILE}" -p k down --remove-orphans
docker compose -f "${REPO_ROOT}/${COMPOSE_FILE}" -p k up -d --remove-orphans

echo "started container ${CONTAINER_NAME}"
echo "ssh: ssh -i \"${HOST_WORKSPACE}/.ssh/id_ed25519\" -p ${SSH_HOST_PORT} k@127.0.0.1"
