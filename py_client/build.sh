#!/bin/bash

# Build script for Temporal Money Transfer Worker - Baseline Version
set -e

# Configuration
IMAGE_NAME="temporal-py-client-ui"
VERSION="v1.0"
REGISTRY="${REGISTRY:-hub.docker.com}"  # Replace with your actual registry
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${VERSION}"

echo "=================================================="
echo "Building Temporal Money Transfer Worker Executor GUI"
echo "=================================================="
echo "Image: ${FULL_IMAGE_NAME}"
echo "Build Date: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo "Git Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo ""

# Build the Docker image
echo "Building Docker image..."
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
docker images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

echo ""
echo "Build completed successfully!"
echo ""
echo "To push to registry:"
echo "  docker push ${FULL_IMAGE_NAME}"
echo "  docker push ${REGISTRY}/${IMAGE_NAME}:latest"
echo ""
echo "To run locally:"
echo "  docker run --rm -e TASK_QUEUE=money-transfer ${IMAGE_NAME}:${VERSION}"
echo ""
echo "To run with custom configuration:"
echo "  docker run --rm \\"
echo "    -e TASK_QUEUE=money-transfer \\"
echo "    -e TEMPORAL_SERVER_URL=temporal-server:7233 \\"
echo "    -e ROUTES_API_URL=http://<your-router-api-url> \\"
echo "    ${IMAGE_NAME}:${VERSION}"