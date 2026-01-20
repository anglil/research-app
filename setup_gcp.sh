#!/bin/bash

# Auto-configure local gcloud path (Now in Google Drive)
export PATH=$PATH:"/Users/anglil/Library/CloudStorage/GoogleDrive-xbeiba@gmail.com/My Drive/tools/google-cloud-sdk/bin"

# 1. Check Project Config
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" == "(unset)" ]; then
    echo "⚠️  No Default GCP Project Detected."
    echo "Please enter your Google Cloud Project ID (found in the dashboard):"
    read -r PROJECT_ID
    
    if [ -z "$PROJECT_ID" ]; then
        echo "❌ Error: Project ID is required. Exiting."
        exit 1
    fi
    
    echo "✅ Setting active project to: $PROJECT_ID"
    gcloud config set project $PROJECT_ID
else
    echo "✅ Using detected Project ID: $PROJECT_ID"
fi

# Configuration
REGION="us-central1"
APP_NAME="research-app"
REPO_NAME="research-repo"
DB_INSTANCE_NAME="research-db-primary"
DB_NAME="research_app"
DB_USER="research_admin"
DB_PASS="ChangeMe123!" # Please change this!

echo "🚀 Starting GCP Deployment for Project: $PROJECT_ID"

# 2. Enable APIs
echo "🔌 Enabling required APIs..."
gcloud services enable run.googleapis.com \
    sqladmin.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    --project=$PROJECT_ID

# 3. Create Artifact Registry
echo "📦 Creating Artifact Registry Repository..."
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID \
    --description="Docker repository for Research App" || echo "Repo might already exist, skipping..."

# 4. Build & Push Image
echo "🔨 Building and Pushing Docker Image..."
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$APP_NAME . --project=$PROJECT_ID

# 5. Create Cloud SQL Instance
echo "🗄️ Creating Cloud SQL Instance (PostgreSQL)... This will take a few minutes."
gcloud sql instances create $DB_INSTANCE_NAME \
    --database-version=POSTGRES_15 \
    --cpu=1 \
    --memory=4GB \
    --region=$REGION \
    --root-password=$DB_PASS \
    --project=$PROJECT_ID || echo "Instance might already exist, skipping..."

# 6. Create Database & User
echo "👤 Creating Database User and DB..."
gcloud sql databases create $DB_NAME --instance=$DB_INSTANCE_NAME --project=$PROJECT_ID || echo "DB exists"
gcloud sql users create $DB_USER --instance=$DB_INSTANCE_NAME --password=$DB_PASS --project=$PROJECT_ID || echo "User exists"

# 7. Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
INSTANCE_CONNECTION_NAME="$PROJECT_ID:$REGION:$DB_INSTANCE_NAME"

# Construct SQL Alchemy Connection String for Unix Socket
DB_URL="postgresql+psycopg2://$DB_USER:$DB_PASS@/$DB_NAME?host=/cloudsql/$INSTANCE_CONNECTION_NAME"

gcloud run deploy $APP_NAME \
    --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$APP_NAME \
    --region=$REGION \
    --allow-unauthenticated \
    --add-cloudsql-instances=$INSTANCE_CONNECTION_NAME \
    --set-env-vars="DATABASE_URL=$DB_URL" \
    --project=$PROJECT_ID \
    --port=8080

echo "✅ Deployment Complete! Check the URL above."
