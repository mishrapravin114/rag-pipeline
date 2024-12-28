# Complete Deployment & Commercial Guide

## How This System Works

### Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend │─────▶│   Backend    │─────▶│   MySQL     │
│  (Next.js) │      │  (FastAPI)   │     │  Database   │
└─────────────┘     └──────────────┘     └─────────────┘
                            │
                            ├─────────────▶┌─────────────┐
                            │              │   Qdrant    │
                            │              │  (Vector DB)│
                            │              └─────────────┘
                            │
                            └─────────────▶┌─────────────┐
                                           │ Google      │
                                           │ Gemini API  │
                                           └─────────────┘
```

### Workflow

1. **Document Upload**
   - User uploads PDF → Backend receives file
   - PyMuPDF extracts text and structure
   - Text is chunked into smaller pieces (3000 chars with 400 overlap)
   - Chunks are embedded using Google Gemini embeddings
   - Embeddings stored in Qdrant vector database
   - Metadata stored in MySQL

2. **Search/Query**
   - User asks question → Query is embedded
   - Hybrid retrieval:
     - **Dense search**: Semantic similarity in Qdrant
     - **Sparse search**: BM25 keyword matching
     - **Reranking**: Cross-encoder reranks results
   - Top documents retrieved
   - Context sent to Gemini LLM
   - Response generated with citations

3. **Background Processing**
   - Large files processed asynchronously
   - Vertex AI batch jobs for heavy processing
   - Pub/Sub for job orchestration
   - Status updates via WebSocket

---

## 🚀 Deployment Options

### Option 1: Cloud Deployment (Recommended for Production)

#### A. Google Cloud Platform (GCP)

**Infrastructure:**
```yaml
Services:
  - Compute Engine (VM): Backend + Frontend
  - Cloud SQL: MySQL database
  - Cloud Storage: File storage
  - Cloud Run: Optional for serverless
  - Vertex AI: Batch processing (optional)
  - Pub/Sub: Job queue (optional)
```

**Steps:**
1. **Create GCP Project**
   ```bash
   gcloud projects create your-project-id
   gcloud config set project your-project-id
   ```

2. **Setup Cloud SQL (MySQL)**
   ```bash
   gcloud sql instances create fda-mysql \
     --database-version=MYSQL_8_0 \
     --tier=db-n1-standard-2 \
     --region=us-central1
   
   gcloud sql databases create fda_rag --instance=fda-mysql
   gcloud sql users create fda_user --instance=fda-mysql --password=your-password
   ```

3. **Deploy Qdrant**
   - Option A: Self-hosted on Compute Engine
   - Option B: Use Qdrant Cloud (managed service)

4. **Deploy Backend**
   ```bash
   # Build Docker image
   docker build -t gcr.io/your-project/fda-backend ./backend
   docker push gcr.io/your-project/fda-backend
   
   # Deploy to Cloud Run
   gcloud run deploy fda-backend \
     --image gcr.io/your-project/fda-backend \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated
   ```

5. **Deploy Frontend**
   ```bash
   cd frontend
   npm run build
   # Deploy to Cloud Storage + Cloud CDN or Cloud Run
   ```

#### B. AWS Deployment

**Infrastructure:**
- EC2: Backend/Frontend servers
- RDS: MySQL database
- S3: File storage
- ECS/EKS: Container orchestration
- OpenSearch/Elasticsearch: Alternative to Qdrant

#### C. Azure Deployment

**Infrastructure:**
- Azure VMs: Backend/Frontend
- Azure Database for MySQL
- Azure Blob Storage
- Azure Container Instances
- Azure Cognitive Search: Alternative to Qdrant

### Option 2: Self-Hosted (VPS/Dedicated Server)

**Requirements:**
- 8GB+ RAM
- 4+ CPU cores
- 100GB+ storage
- Ubuntu 20.04+ or similar

**Steps:**
```bash
# 1. Install Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo apt-get install docker-compose-plugin

# 2. Clone repository
git clone <repo-url>
cd rag-pipeline-master

# 3. Create .env file
cp .env.example .env
# Edit .env with your configuration

# 4. Start services
docker-compose -f docker-compose.prod.yml up -d

# 5. Setup reverse proxy (Nginx)
sudo apt-get install nginx
# Configure Nginx to proxy to backend:8090 and frontend:3001
```

### Option 3: Kubernetes Deployment

**Files needed:**
- `k8s/backend-deployment.yaml`
- `k8s/frontend-deployment.yaml`
- `k8s/mysql-deployment.yaml`
- `k8s/qdrant-deployment.yaml`
- `k8s/services.yaml`
- `k8s/configmap.yaml`
- `k8s/secrets.yaml`

---

## 💰 Cost Estimation

### Monthly Costs Breakdown

#### Small Scale (100-1000 users/month)

| Service | Provider | Cost/Month | Notes |
|---------|----------|------------|-------|
| **Compute** | GCP/AWS/Azure | $50-100 | 2 vCPU, 8GB RAM VM |
| **Database** | Cloud SQL/RDS | $30-50 | db-n1-standard-1 |
| **Vector DB** | Self-hosted | $20-30 | Qdrant on same VM |
| **Storage** | Cloud Storage/S3 | $5-10 | 50GB storage |
| **Google Gemini API** | Google | $50-200 | Based on usage |
| **Bandwidth** | Cloud Provider | $10-20 | Data transfer |
| **Domain/SSL** | Various | $5-10 | Domain + certificate |
| **Total** | | **$170-420/month** | |

#### Medium Scale (1000-10000 users/month)

| Service | Provider | Cost/Month | Notes |
|---------|----------|------------|-------|
| **Compute** | GCP/AWS/Azure | $200-400 | 4 vCPU, 16GB RAM |
| **Database** | Cloud SQL/RDS | $100-200 | db-n1-standard-2 |
| **Vector DB** | Qdrant Cloud | $100-200 | Managed service |
| **Storage** | Cloud Storage/S3 | $20-50 | 200GB storage |
| **Google Gemini API** | Google | $200-1000 | Higher usage |
| **CDN** | CloudFlare/Cloud CDN | $20-50 | Content delivery |
| **Bandwidth** | Cloud Provider | $50-100 | Data transfer |
| **Monitoring** | Datadog/New Relic | $50-100 | Optional |
| **Total** | | **$740-2000/month** | |

#### Large Scale (10000+ users/month)

| Service | Provider | Cost/Month | Notes |
|---------|----------|------------|-------|
| **Compute** | GCP/AWS/Azure | $500-1000 | Multiple instances |
| **Database** | Cloud SQL/RDS | $300-600 | High availability |
| **Vector DB** | Qdrant Cloud | $300-500 | Enterprise plan |
| **Storage** | Cloud Storage/S3 | $100-200 | 1TB+ storage |
| **Google Gemini API** | Google | $1000-5000 | Enterprise usage |
| **CDN** | CloudFlare/Cloud CDN | $100-200 | |
| **Bandwidth** | Cloud Provider | $200-500 | |
| **Monitoring** | Datadog/New Relic | $200-500 | |
| **Load Balancer** | Cloud Provider | $20-50 | |
| **Total** | | **$2720-8650/month** | |

### Cost Optimization Tips

1. **Use Reserved Instances**: Save 30-40% on compute
2. **Auto-scaling**: Scale down during low traffic
3. **Caching**: Reduce API calls to Gemini
4. **Self-host Qdrant**: Save on managed service costs
5. **Use cheaper regions**: Some regions are 20-30% cheaper
6. **Optimize embeddings**: Cache frequently used queries
7. **Batch processing**: Process documents in batches

### Google Gemini API Pricing (as of 2024)

- **Gemini 2.0 Flash**: 
  - Input: $0.075 per 1M tokens
  - Output: $0.30 per 1M tokens
- **Embeddings (text-embedding-004)**:
  - $0.10 per 1M tokens

**Example calculation:**
- 1000 queries/day × 30 days = 30,000 queries/month
- Average: 2000 tokens input, 500 tokens output per query
- Cost: (30,000 × 2 × $0.075/1M) + (30,000 × 0.5 × $0.30/1M) = $4.50 + $4.50 = **$9/month**

---

## 📜 Licensing & Commercial Use

### Current License Status

✅ **MIT License** - Added on December 25, 2024
- Copyright (c) 2024 Pravin Mishra
- Permissive license allowing commercial use, modification, and distribution
- See [LICENSE](LICENSE) file for full terms

### What This Means:

1. **Without a license, the code is under "All Rights Reserved"**
   - You cannot legally use, modify, or distribute it
   - You cannot sell it
   - You need explicit permission from the copyright holder

2. **To Sell/Commercialize:**
   - **Option A**: Get explicit permission from original author
   - **Option B**: Add your own license (if you own the code)
   - **Option C**: Rewrite significant portions to create derivative work

### Recommended Licenses for Commercial Use

#### If You Own the Code:

1. **Proprietary License** (Full commercial rights)
   ```
   Copyright (c) 2024 [Your Company]
   All rights reserved.
   ```

2. **Dual License** (Open source + Commercial)
   - AGPL for open source
   - Commercial license for proprietary use

3. **MIT/Apache 2.0** (If you want to allow others to use it)

#### If You Don't Own the Code:

1. **Contact the original author** for licensing agreement
2. **Create a commercial license agreement**
3. **Consider creating a fork** with significant modifications

### Dependencies & Their Licenses

All dependencies are **open source** and allow commercial use:

| Dependency | License | Commercial Use |
|------------|---------|----------------|
| FastAPI | MIT | ✅ Yes |
| LangChain | MIT | ✅ Yes |
| Qdrant | Apache 2.0 | ✅ Yes |
| PyMuPDF | AGPL/Commercial | ⚠️ Check commercial license |
| Google APIs | Proprietary | ✅ Yes (with API key) |
| MySQL | GPL/Commercial | ⚠️ GPL requires open source, or buy commercial |
| Next.js | MIT | ✅ Yes |
| React | MIT | ✅ Yes |

**⚠️ Important Notes:**
- **PyMuPDF (AGPL)**: If you modify it, you must open source your changes OR buy commercial license
- **MySQL (GPL)**: If you distribute MySQL with your product, you may need commercial license OR use MariaDB (GPL compatible)

### Recommendations for Commercial Deployment

1. **Use MariaDB instead of MySQL** (GPL compatible, no commercial license needed)
2. **Buy PyMuPDF commercial license** if you modify it ($2,000-5,000 one-time)
3. **Use PostgreSQL instead of MySQL** (PostgreSQL license, more permissive)
4. **Ensure all dependencies are properly licensed**

---

## 🔗 Dependencies on Other Projects

### External Services (Required)

1. **Google Gemini API** ⚠️ **CRITICAL DEPENDENCY**
   - **Required**: Yes
   - **Cost**: Pay-per-use
   - **Alternative**: OpenAI API, Anthropic Claude, Local LLM (Ollama)
   - **Impact**: System won't work without LLM

2. **Vector Database (Qdrant)**
   - **Required**: Yes
   - **Options**: 
     - Self-hosted (free)
     - Qdrant Cloud (paid)
     - Alternatives: Pinecone, Weaviate, ChromaDB

3. **Relational Database (MySQL)**
   - **Required**: Yes
   - **Alternatives**: PostgreSQL, MariaDB, SQLite (for small scale)

### External Services (Optional)

1. **Google Cloud Platform**
   - Pub/Sub: For job queuing
   - Vertex AI: For batch processing
   - Cloud Storage: For file storage
   - **Can be replaced**: Use Redis/RabbitMQ, local processing, S3

2. **Google OAuth**
   - For user authentication
   - **Can be replaced**: Auth0, Firebase Auth, custom JWT

### Open Source Dependencies

All Python/Node.js packages are open source and can be:
- ✅ Used commercially (with proper licenses)
- ✅ Modified
- ✅ Distributed (check individual licenses)

**Key Dependencies:**
- FastAPI, LangChain, Qdrant Client, PyMuPDF, etc.
- All have permissive licenses (MIT, Apache 2.0)

### Can You Remove Dependencies?

**Yes, but with effort:**

1. **Replace Google Gemini** → Use OpenAI/Anthropic/Local LLM
   - Modify: `src/utils/llm_util.py`
   - Estimated effort: 1-2 weeks

2. **Replace Qdrant** → Use Pinecone/Weaviate/ChromaDB
   - Modify: `src/utils/qdrant_util.py`
   - Estimated effort: 2-3 weeks

3. **Replace MySQL** → Use PostgreSQL
   - Modify: Database connection strings
   - Estimated effort: 1 week

4. **Remove GCP Services** → Use alternatives
   - Replace Pub/Sub with Redis/RabbitMQ
   - Replace Vertex AI with local processing
   - Estimated effort: 2-4 weeks

---

## ✅ Checklist Before Commercial Deployment

- [ ] **Legal**
  - [ ] Determine code ownership
  - [ ] Add appropriate license
  - [ ] Review all dependency licenses
  - [ ] Get PyMuPDF commercial license (if needed)
  - [ ] Get MySQL commercial license OR switch to PostgreSQL/MariaDB

- [ ] **Infrastructure**
  - [ ] Choose deployment platform (GCP/AWS/Azure/Self-hosted)
  - [ ] Setup domain and SSL certificate
  - [ ] Configure monitoring and logging
  - [ ] Setup backup strategy
  - [ ] Configure auto-scaling

- [ ] **Security**
  - [ ] Secure API keys and secrets
  - [ ] Enable HTTPS
  - [ ] Configure CORS properly
  - [ ] Setup rate limiting
  - [ ] Implement proper authentication
  - [ ] Regular security audits

- [ ] **Performance**
  - [ ] Load testing
  - [ ] Database optimization
  - [ ] Caching strategy
  - [ ] CDN setup
  - [ ] Query optimization

- [ ] **Compliance**
  - [ ] GDPR compliance (if EU users)
  - [ ] Data privacy policies
  - [ ] Terms of service
  - [ ] User data handling

---

## 📞 Support & Resources

- **Documentation**: See README.md
- **API Docs**: Available at `/docs` when running
- **Issues**: Check GitHub issues (if public repo)
- **Community**: LangChain Discord, FastAPI Discord

---

**Last Updated**: December 25, 2024

