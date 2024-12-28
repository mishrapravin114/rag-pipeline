#!/bin/bash
#
# This script automates the setup of GCP resources required for the
# Vertex AI Batch Prediction indexing pipeline.
#
# Prerequisites:
#   - Google Cloud SDK (gcloud) installed and authenticated.
#   - A GCP Project selected (gcloud config set project YOUR_PROJECT_ID).
#   - Permissions to create the resources below (e.g., Project Owner/Editor).
#

set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration ---
# IMPORTANT: Replace these with your desired names and settings.
GCP_PROJECT_ID="$(gcloud config get-value project)"
REGION="us-central1" # e.g., us-central1, europe-west2
BUCKET_NAME="rag-pipeline-batch-embeddings-${GCP_PROJECT_ID}" # Must be globally unique
PUBSUB_TOPIC="batch-indexing-jobs"
SERVICE_ACCOUNT_NAME="vertex-ai-batch-processor"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

echo "--- Starting GCP Resource Setup for Project: ${GCP_PROJECT_ID} in Region: ${REGION} ---"

# --- 1. Enable Required APIs ---
echo "Enabling required GCP APIs..."
gcloud services enable \
  aiplatform.googleapis.com \
  pubsub.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com

echo "APIs enabled successfully."

# --- 2. Create a Google Cloud Storage (GCS) Bucket ---
echo "Creating GCS Bucket: gs://${BUCKET_NAME}..."
# Check if the bucket already exists
if gsutil ls -b "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
  echo "Bucket gs://${BUCKET_NAME} already exists. Skipping creation."
else
  gsutil mb -p "${GCP_PROJECT_ID}" -l "${REGION}" "gs://${BUCKET_NAME}"
  echo "GCS Bucket created successfully."
fi

# --- 3. Create a Pub/Sub Topic ---
echo "Creating Pub/Sub Topic: ${PUBSUB_TOPIC}..."
if gcloud pubsub topics describe "${PUBSUB_TOPIC}" >/dev/null 2>&1; then
  echo "Pub/Sub Topic ${PUBSUB_TOPIC} already exists. Skipping creation."
else
  gcloud pubsub topics create "${PUBSUB_TOPIC}"
  echo "Pub/Sub Topic created successfully."
fi

# --- 4. Create a Service Account ---
echo "Creating Service Account: ${SERVICE_ACCOUNT_NAME}..."
if gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" >/dev/null 2>&1; then
  echo "Service Account ${SERVICE_ACCOUNT_EMAIL} already exists. Skipping creation."
else
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
    --display-name="Service Account for Vertex AI Batch Indexing"
  echo "Service Account created successfully."
  sleep 10
fi

# --- 5. Grant IAM Permissions to the Service Account ---
echo "Granting necessary IAM roles to the Service Account..."

# Role for Vertex AI: To create and monitor batch prediction jobs.
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/aiplatform.user"

# Role for GCS: To read input files and write output files.
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/storage.objectAdmin"

# Role for Pub/Sub: To subscribe to the topic for new jobs.
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/pubsub.subscriber"

echo "IAM roles granted successfully."

# --- 6. Create and download a key for the Service Account ---
echo "Creating and downloading a service account key..."
if [ -f "gcp_service_account_key.json" ]; then
  echo "Service account key file already exists. Skipping creation."
else
  gcloud iam service-accounts keys create "gcp_service_account_key.json" \
    --iam-account="${SERVICE_ACCOUNT_EMAIL}"
fi

echo "Service account key saved to gcp_service_account_key.json."
echo "IMPORTANT: Secure this file and use it to authenticate your application."

echo "--- GCP Resource Setup Complete! ---"
echo
echo "--- Summary of Created Resources ---"
echo "GCS Bucket: gs://${BUCKET_NAME}"
echo "Pub/Sub Topic: ${PUBSUB_TOPIC}"
echo "Service Account: ${SERVICE_ACCOUNT_EMAIL}"
echo "Service Account Key File: gcp_service_account_key.json"
echo
echo "Next Steps:"
echo "1. Move 'gcp_service_account_key.json' to a secure location."
echo "2. Update your application's environment variables with the resource names."
echo "   - GCS_BUCKET_NAME=${BUCKET_NAME}"
echo "   - GCP_PROJECT_ID=${GCP_PROJECT_ID}"
echo "   - GCP_REGION=${REGION}"
echo "   - PUBSUB_TOPIC_ID=${PUBSUB_TOPIC}"
echo "   - GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp_service_account_key.json"
