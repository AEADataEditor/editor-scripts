#!/bin/bash

# Exit on any error
set -e

# Configuration
IMAGE_NAME="html-to-pdf"
DOCKER_HUB_USER="aeadataeditor"
TAG=${1:-latest}

echo "Building Docker image: ${DOCKER_HUB_USER}/${IMAGE_NAME}:${TAG}"

# Build the Docker image
docker build -t ${IMAGE_NAME} .
docker tag ${IMAGE_NAME} ${DOCKER_HUB_USER}/${IMAGE_NAME}:${TAG}

echo "Pushing to Docker Hub..."
docker push ${DOCKER_HUB_USER}/${IMAGE_NAME}:${TAG}

echo "Build and push complete: ${DOCKER_HUB_USER}/${IMAGE_NAME}:${TAG}"