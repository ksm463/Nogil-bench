#!/bin/bash

CONTAINER_NAME="nogil-bench"
IMAGE_NAME="nogil-bench"
TAG="0.1"

project_path=$(pwd)

docker run \
    -d \
    -p 8000:8000 \
    --name ${CONTAINER_NAME} \
    -v ${project_path}:/app \
    -v nogil-bench-venv:/app/.venv \
    -e PYTHON_GIL=0 \
    -w /app \
    ${IMAGE_NAME}:${TAG} \
    tail -f /dev/null
