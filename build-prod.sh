#!/bin/bash
set -e

echo "🚀 Starting production build with optimizations..."

# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📦 Build Configuration:${NC}"
echo "  - Docker BuildKit: ENABLED"
echo "  - Parallel builds: ENABLED"
echo "  - Build context: Optimized with .dockerignore"

# Pull existing images for cache (optional, useful for CI/CD)
echo -e "\n${BLUE}📥 Pulling existing images for cache...${NC}"
docker-compose -f docker-compose.prod.yml pull || true

# Build all services in parallel
echo -e "\n${BLUE}🔨 Building services in parallel...${NC}"
time docker-compose -f docker-compose.prod.yml build \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --parallel

echo -e "\n${GREEN}✅ Build completed successfully!${NC}"

# Show image sizes
echo -e "\n${BLUE}📊 Image sizes:${NC}"
docker images | grep -E "(fda-backend|fda-frontend|REPOSITORY)" | head -4

# Optional: Remove dangling images
echo -e "\n${BLUE}🧹 Cleaning up dangling images...${NC}"
docker image prune -f

echo -e "\n${GREEN}🎉 Production build ready!${NC}"
echo -e "Run ${BLUE}docker-compose -f docker-compose.prod.yml up -d${NC} to start the services."