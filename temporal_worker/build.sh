#!/bin/bash

# Build script for Temporal Money Transfer Worker - Sandbox
set -e

# Configuration
IMAGE_NAME="temporal-money-transfer"
VERSION="sandbox"
REGISTRY="${REGISTRY:-hub.docker.com}"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${VERSION}"

echo "=================================================="
echo "Building Temporal Money Transfer Worker (Sandbox)"
echo "=================================================="
echo "Image: ${FULL_IMAGE_NAME}"
echo "Build Date: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo "Git Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo ""

# Build the Docker image
echo "Building Docker image..."
cd temporal_worker
docker build \
    --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    --build-arg VERSION="${VERSION}" \
    --build-arg GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
    -t "${IMAGE_NAME}:${VERSION}" \
    -t "${IMAGE_NAME}:latest" \
    .

echo "✅ Docker image built successfully!"

# Tag for registry
echo "Tagging image for registry..."
docker tag "${IMAGE_NAME}:${VERSION}" "${FULL_IMAGE_NAME}"
docker tag "${IMAGE_NAME}:latest" "${REGISTRY}/${IMAGE_NAME}:latest"

echo "✅ Image tagged for registry"

# Show image details
echo ""
echo "Image Details:"
docker images "${IMAGE_NAME}"  --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

echo ""
echo "Build completed successfully!"
echo ""
echo "To push to registry:"
echo "  docker push ${FULL_IMAGE_NAME}"
echo "  docker push ${REGISTRY}/${IMAGE_NAME}:latest"