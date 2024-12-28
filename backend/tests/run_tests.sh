#!/bin/bash
# Run backend tests

echo "Running backend tests for metadata groups..."

# Navigate to backend directory
cd /home/pravin/Documents/rag-pipeline/backend

# Install pytest if not already installed
pip install pytest pytest-cov

# Run tests with coverage
echo "Running unit tests..."
python -m pytest tests/test_metadata_group_service.py -v --cov=src.api.services.metadata_group_service

# Run API integration tests
echo -e "\nRunning API integration tests..."
python tests/test_metadata_groups_api.py

echo -e "\nTests completed!"