#!/bin/bash

# Script to fix GCP configuration in production environment

echo "=========================================="
echo "GCP Configuration Fix for Production"
echo "=========================================="

# Check if running in production
if [ ! -f "/.dockerenv" ] && [ "$1" != "--force" ]; then
    echo "This script should be run inside the production container or with --force flag"
    echo "Usage: ./fix_production_gcp_config.sh [--force]"
    exit 1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "\n${YELLOW}1. Checking current environment variables...${NC}"
echo "GCP_PROJECT_ID: ${GCP_PROJECT_ID:-NOT SET}"
echo "PUBSUB_TOPIC_ID: ${PUBSUB_TOPIC_ID:-NOT SET}"
echo "GCS_BUCKET_NAME: ${GCS_BUCKET_NAME:-NOT SET}"
echo "GOOGLE_APPLICATION_CREDENTIALS: ${GOOGLE_APPLICATION_CREDENTIALS:-NOT SET}"

echo -e "\n${YELLOW}2. Checking if GCP service account key exists...${NC}"
if [ -f "/app/gcp-service-account-key.json" ]; then
    echo -e "${GREEN}✓ Service account key found at /app/gcp-service-account-key.json${NC}"
elif [ -f "./gcp-service-account-key.json" ]; then
    echo -e "${GREEN}✓ Service account key found at ./gcp-service-account-key.json${NC}"
else
    echo -e "${RED}✗ Service account key not found!${NC}"
    echo "Please ensure gcp-service-account-key.json exists in the project root"
fi

echo -e "\n${YELLOW}3. Checking .env files...${NC}"
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env file exists${NC}"
    grep -E "GCP_PROJECT_ID|PUBSUB_TOPIC_ID|GCS_BUCKET_NAME" .env || echo "No GCP variables found in .env"
fi

if [ -f ".env.production" ]; then
    echo -e "${GREEN}✓ .env.production file exists${NC}"
    grep -E "GCP_PROJECT_ID|PUBSUB_TOPIC_ID|GCS_BUCKET_NAME" .env.production || echo "No GCP variables found in .env.production"
fi

echo -e "\n${YELLOW}4. Recommended actions:${NC}"
echo "1. Ensure the following variables are set in your production .env file:"
echo "   GCP_PROJECT_ID=rag-pipeline-464514"
echo "   PUBSUB_TOPIC_ID=batch-indexing-jobs"
echo "   GCS_BUCKET_NAME=rag-pipeline-batch-embeddings-rag-pipeline-464514"
echo "   GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-service-account-key.json"
echo ""
echo "2. Restart the backend container after updating .env:"
echo "   docker-compose -f docker-compose.prod.yml restart backend"
echo ""
echo "3. Also restart the vertex-ai-batch-processor container:"
echo "   docker-compose -f docker-compose.prod.yml restart vertex-ai-batch-processor"

echo -e "\n${YELLOW}5. Testing GCP connection...${NC}"
if command -v python3 &> /dev/null; then
    python3 -c "
import os
try:
    from google.cloud import pubsub_v1
    project_id = os.getenv('GCP_PROJECT_ID')
    topic_id = os.getenv('PUBSUB_TOPIC_ID')
    if project_id and topic_id:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, topic_id)
        print('✓ Successfully initialized Pub/Sub client')
        print(f'  Topic path: {topic_path}')
    else:
        print('✗ Missing GCP_PROJECT_ID or PUBSUB_TOPIC_ID')
except Exception as e:
    print(f'✗ Error: {e}')
" 2>/dev/null || echo "Python test skipped (dependencies not available)"
fi

echo -e "\n${GREEN}Script completed!${NC}"