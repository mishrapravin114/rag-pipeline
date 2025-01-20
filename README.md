# RAG Pipeline - FDA Document Processing System

A comprehensive Retrieval-Augmented Generation (RAG) pipeline for processing and querying FDA documents. This system enables intelligent document search, metadata extraction, and conversational AI interactions with pharmaceutical regulatory documents.

## 🚀 Features

- **Document Processing**: Upload and process PDF documents with automatic text extraction and chunking
- **Vector Search**: Semantic search using Qdrant vector database with hybrid retrieval (BM25 + semantic)
- **LLM Integration**: Powered by Google Gemini for intelligent question answering
- **Metadata Extraction**: Automated extraction of drug information, therapeutic areas, and regulatory metadata
- **Multi-Collection Support**: Organize documents into collections (FDA, EMA, HTA, etc.)
- **RESTful API**: FastAPI-based backend with comprehensive endpoints
- **Web Interface**: Next.js frontend for document management and chat interface
- **Background Processing**: Asynchronous document indexing and processing
- **Authentication**: JWT-based authentication with Google OAuth support

## 📋 Prerequisites

### For Docker Setup:
- Docker (version 20.10+)
- Docker Compose (version 2.0+)
- 8GB+ RAM recommended
- 20GB+ free disk space

### For Local Setup:
- Python 3.10 or 3.11
- MySQL 8.0 (or use Docker for MySQL)
- Qdrant (or use Docker for Qdrant)
- Node.js 18+ (for frontend)
- Google Cloud Platform account (for Gemini API)

## 🛠️ Installation & Setup

### Option 1: Running with Docker (Recommended)

#### 1. Clone the Repository
```bash
git clone <repository-url>
cd rag-pipeline-master
```

#### 2. Create Environment File
Create a `.env` file in the root directory:
```bash
# Database Configuration
DATABASE_URL=mysql+pymysql://fda_user:fda_password@localhost:3307/fda_rag

# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Google API Configuration
GOOGLE_API_KEY=your-google-api-key-here
SECRET_KEY=your-secret-key-here

# Optional: GCP Configuration (for Pub/Sub and Cloud Storage)
GCP_PROJECT_ID=your-gcp-project-id
PUBSUB_TOPIC_ID=your-pubsub-topic
GCS_BUCKET_NAME=your-gcs-bucket

# Frontend Configuration
FRONTEND_URL=http://localhost:3001
BACKEND_URL=http://localhost:8090
```

#### 3. Create Required Secret Files (Optional - for GCP features)
```bash
# Place your GCP service account key
cp your-service-account-key.json ./gcp_service_account_key.json

# Place your Google OAuth client secrets
cp your-client-secrets.json ./google_client_secrets.json
```

#### 4. Start Services with Docker Compose

**For Development:**
```bash
# Start MySQL and Qdrant only
docker-compose up -d mysql qdrant

# Or start all services (backend + frontend)
docker-compose up -d
```

**For Production:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

#### 5. Verify Services
```bash
# Check service status
docker-compose ps

# Check backend health
curl http://localhost:8090/api/health

# Check Qdrant
curl http://localhost:6333/collections

# Check MySQL
docker exec -it fda-mysql mysql -u fda_user -pfda_password -e "SHOW DATABASES;"
```

#### 6. Access the Application
- **Backend API**: http://localhost:8090
- **Frontend**: http://localhost:3001
- **API Documentation**: http://localhost:8090/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard

### Option 2: Running Without Docker (Local Development)

#### 1. Setup MySQL Database

**Using Docker for MySQL only:**
```bash
docker-compose up -d mysql
```

**Or install MySQL locally:**
```bash
# macOS
brew install mysql
brew services start mysql

# Create database
mysql -u root -p
CREATE DATABASE fda_rag;
CREATE USER 'fda_user'@'localhost' IDENTIFIED BY 'fda_password';
GRANT ALL PRIVILEGES ON fda_rag.* TO 'fda_user'@'localhost';
FLUSH PRIVILEGES;
```

#### 2. Setup Qdrant

**Using Docker for Qdrant only:**
```bash
docker-compose up -d qdrant
```

**Or install Qdrant locally:**
```bash
# Using Docker (recommended)
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest

# Or download binary from https://qdrant.tech/documentation/guides/installation/
```

#### 3. Setup Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file in backend directory (optional, can use root .env)
cat > .env << EOF
DATABASE_URL=mysql+pymysql://fda_user:fda_password@localhost:3307/fda_rag
QDRANT_HOST=localhost
QDRANT_PORT=6333
GOOGLE_API_KEY=your-google-api-key-here
SECRET_KEY=your-secret-key-here
FRONTEND_URL=http://localhost:3001
BACKEND_URL=http://localhost:8090
EOF

# Set environment variables (if not using .env)
export DATABASE_URL="mysql+pymysql://fda_user:fda_password@localhost:3307/fda_rag"
export QDRANT_HOST="localhost"
export QDRANT_PORT="6333"
export GOOGLE_API_KEY="your-google-api-key-here"

# Run the backend
python main.py
```

The backend will start on `http://localhost:8090`

#### 4. Setup Frontend (Optional)

```bash
cd frontend

# Install dependencies
npm install
# or
pnpm install

# Create .env.local file
cat > .env.local << EOF
NEXT_PUBLIC_API_URL=http://localhost:8090
NEXT_PUBLIC_WS_URL=ws://localhost:8090
NEXT_PUBLIC_GOOGLE_API_KEY=your-google-api-key-here
EOF

# Run development server
npm run dev
# or
pnpm dev
```

The frontend will start on `http://localhost:3001`

## 📁 Project Structure

```
rag-pipeline-master/
├── backend/                 # FastAPI backend application
│   ├── src/
│   │   ├── api/            # API routes and services
│   │   ├── database/       # Database models and configuration
│   │   ├── services/       # Business logic services
│   │   └── utils/          # Utility functions
│   ├── scripts/            # Background processing scripts
│   ├── migrations/         # Database migrations
│   ├── main.py            # FastAPI application entry point
│   └── requirements.txt   # Python dependencies
├── frontend/               # Next.js frontend application
├── docker-compose.yml      # Docker Compose for development
├── docker-compose.prod.yml # Docker Compose for production
├── README.md              # This file
└── DEPLOYMENT_GUIDE.md    # Deployment and commercial guide
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | MySQL connection string | `mysql+pymysql://fda_user:fda_password@localhost:3307/fda_rag` | Yes |
| `QDRANT_HOST` | Qdrant server hostname | `localhost` | Yes |
| `QDRANT_PORT` | Qdrant HTTP port | `6333` | Yes |
| `GOOGLE_API_KEY` | Google Gemini API key | - | **Yes** |
| `SECRET_KEY` | JWT secret key | - | **Yes** |
| `FRONTEND_URL` | Frontend application URL | `http://localhost:3001` | No |
| `BACKEND_URL` | Backend API URL | `http://localhost:8090` | No |
| `LLM_GEMINI_MODEL` | Gemini model to use | `gemini-2.0-flash` | No |
| `CHUNK_SIZE` | Document chunk size | `3000` | No |
| `CHUNK_OVERLAP` | Chunk overlap size | `400` | No |

**Note**: `GOOGLE_API_KEY` is required for the system to function. Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey).

### Database Configuration

The system uses MySQL 8.0 with the following default settings:
- Database: `fda_rag`
- User: `fda_user`
- Password: `fda_password`
- Port: `3307` (Docker) or `3306` (local)

### Qdrant Configuration

Qdrant is used as the vector database:
- HTTP Port: `6333`
- gRPC Port: `6334`
- Default collection: `fda_documents`

## 🚀 Usage

### API Endpoints

#### Health Check
```bash
GET /api/health
```

#### Upload Document
```bash
POST /api/upload
Content-Type: multipart/form-data
```

#### Search Documents
```bash
POST /api/search
{
  "query": "your search query",
  "collection_id": 1,
  "limit": 10
}
```

#### Chat with Documents
```bash
POST /api/chat
{
  "message": "What is the efficacy of drug X?",
  "collection_id": 1,
  "conversation_id": "optional-conversation-id"
}
```

#### Get Collections
```bash
GET /api/collections
```

See full API documentation at `http://localhost:8090/docs` when the server is running.

### Example: Upload and Query a Document

1. **Upload a PDF:**
```bash
curl -X POST "http://localhost:8090/api/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf" \
  -F "collection_id=1"
```

2. **Wait for processing** (check status via API)

3. **Query the document:**
```bash
curl -X POST "http://localhost:8090/api/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "What are the key findings?",
    "collection_id": 1
  }'
```

## 🧪 Testing

```bash
cd backend
source venv/bin/activate
pytest tests/
```

## 📊 Monitoring

### Health Checks
- Backend: `http://localhost:8090/api/health`
- Qdrant: `http://localhost:6333/`
- MySQL: `docker exec fda-mysql mysqladmin ping -h localhost`

### Logs

**Docker:**
```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f backend
docker-compose logs -f mysql
docker-compose logs -f qdrant
```

**Local:**
- Backend logs: Check console output or `backend/output/logs/`
- MySQL logs: Check MySQL log files
- Qdrant logs: Check Qdrant console output

## 🔒 Security

- Use strong `SECRET_KEY` for JWT tokens
- Keep `GOOGLE_API_KEY` secure and never commit to version control
- Use environment variables for sensitive configuration
- Enable HTTPS in production
- Configure CORS properly for production

## 🐛 Troubleshooting

### Backend won't start
- Check MySQL is running: `docker-compose ps mysql`
- Check Qdrant is running: `curl http://localhost:6333/`
- Verify environment variables are set correctly
- Check logs: `docker-compose logs backend`

### Database connection errors
- Verify MySQL is accessible: `mysql -u fda_user -pfda_password -h localhost -P 3307`
- Check DATABASE_URL format is correct
- Ensure database `fda_rag` exists

### Qdrant connection errors
- Verify Qdrant is running: `curl http://localhost:6333/collections`
- Check QDRANT_HOST and QDRANT_PORT environment variables
- Ensure ports 6333 and 6334 are not blocked

### Import errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.10+)
- Verify virtual environment is activated

## 📝 Development

### Running Migrations
```bash
cd backend
python -m migrations.add_collections_tables
```

### Code Style
- Follow PEP 8 for Python code
- Use type hints where possible
- Document functions and classes

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

**MIT License**

Copyright (c) 2024 Pravin Mishra

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

See [LICENSE](LICENSE) file for full terms.

## 🔗 Dependencies

### Critical Dependencies
- **Google Gemini API**: Required for LLM and embeddings (usage-based pricing)
- **Qdrant**: Vector database (can be self-hosted or cloud)
- **MySQL**: Relational database (can be replaced with PostgreSQL/MariaDB)

### Optional Dependencies
- **Google Cloud Platform**: For Pub/Sub, Vertex AI, Cloud Storage (optional)
- **Google OAuth**: For authentication (can be replaced with other auth providers)

All code dependencies are open source with permissive licenses (MIT, Apache 2.0). See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed dependency information and alternatives.

## 🙏 Acknowledgments

- FastAPI for the web framework
- Qdrant for vector database
- Google Gemini for LLM capabilities
- LangChain for RAG orchestration

## 🚀 Deployment & Production

For detailed deployment instructions, cost estimation, and commercial use information, see the **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)**.

### Quick Deployment Options

- **Docker Compose** (Recommended for quick start)
  ```bash
  docker-compose -f docker-compose.prod.yml up -d
  ```

- **Cloud Platforms**: GCP, AWS, Azure (see deployment guide)
- **Self-Hosted**: VPS or dedicated server
- **Kubernetes**: For enterprise scale

### Estimated Monthly Costs

| Scale | Users/Month | Estimated Cost |
|-------|------------|----------------|
| Small | 100-1,000 | $170-420 |
| Medium | 1,000-10,000 | $740-2,000 |
| Large | 10,000+ | $2,720-8,650 |

*Costs include infrastructure, database, vector DB, and Google Gemini API usage*

### Commercial Use

✅ **This project is licensed under MIT License** - Commercial use is permitted.

**Important Notes:**
- Requires Google Gemini API key (usage-based pricing)
- Some dependencies may require commercial licenses (see deployment guide)
- Consider PostgreSQL/MariaDB instead of MySQL for GPL compliance

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check the documentation at `/docs` endpoint
- Review logs for error messages
- See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for deployment help

---

**Last Updated**: December 25, 2024

