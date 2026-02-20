#!/bin/bash

IMAGE_NAME="nogil-bench"
TAG="0.1"

docker build --progress=plain -t ${IMAGE_NAME}:${TAG} .
