#!/bin/bash

# Login and get token
TOKEN=$(curl -s -X POST "http://localhost:8090/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' | jq -r '.access_token')

echo "Token: $TOKEN"

# Reindex document 16
curl -X POST "http://localhost:8090/api/collections/1/reindex" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"file_ids": [16]}' | jq