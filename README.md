# ReplantWorld - Solana Carbon Credit NFT Platform

A comprehensive platform for carbon credit NFTs built on Solana blockchain, featuring compressed NFTs for scalability and cost-effectiveness.

## 🌟 Project Overview

ReplantWorld is a next-generation carbon credit platform that leverages Solana's compressed NFT technology to create scalable, cost-effective carbon credit tokens. The platform enables tree planting organizations to mint carbon credits as NFTs and allows users to purchase and trade these credits transparently.

## 🏗️ Architecture

### Core Components
- **Backend**: Django REST API with PostgreSQL and Redis
- **Frontend**: React with TypeScript and Vite
- **Blockchain**: Solana (compressed NFTs via Metaplex Bubblegum)
- **Infrastructure**: Docker Compose for development

### Key Features
- Compressed NFT minting for cost-effective carbon credits
- Real-time carbon calculation using Chapman-Richards growth models
- Sei blockchain data migration tools
- Comprehensive health monitoring and logging
- Scalable microservices architecture

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)
- Solana CLI (for blockchain operations)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd NFT-REPLANT-WORLD
   ```

2. **Start the development environment**
   ```bash
   cd infra
   docker-compose up -d
   ```

3. **Set up Solana CLI**
   ```bash
   # Windows
   .\setup-solana.ps1

   # Linux/Mac
   ./setup-solana.sh
   ```

4. **Access the applications**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Health Check: http://localhost:8000/api/healthz/

## 📁 Project Structure

```
NFT-REPLANT-WORLD/
├── backend/                 # Django REST API
│   ├── core/               # Django project settings
│   ├── common/             # Shared utilities and health checks
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile         # Backend container config
├── frontend/               # React TypeScript application
│   ├── src/               # Source code
│   │   ├── components/    # React components
│   │   └── utils/         # Utility functions
│   ├── package.json       # Node.js dependencies
│   └── Dockerfile         # Frontend container config
├── infra/                  # Infrastructure and deployment
│   ├── docker-compose.yml # Development environment
│   ├── setup-solana.ps1   # Solana CLI setup (Windows)
│   └── setup-solana.sh    # Solana CLI setup (Linux/Mac)
└── README.md              # This file
```

## 🔧 Development

### Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### Database Operations
```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Access database
docker-compose exec postgres psql -U postgres -d replantworld
```

## 🏥 Health Monitoring

The platform includes comprehensive health monitoring:

- **Backend Health**: `/api/healthz/` - Checks database and Redis connectivity
- **Frontend Health**: Built-in health check component
- **Structured Logging**: JSON-formatted logs with structured data
- **Error Boundaries**: React error boundaries for graceful error handling

## 🔐 Environment Configuration

### Development Environment Variables
```bash
# Database
DB_NAME=replantworld
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

## 🧪 Testing

### Backend Tests
```bash
cd backend
python manage.py test
```

### Frontend Tests
```bash
cd frontend
npm run test
```

## 📊 Monitoring and Logging

### Structured Logging
The backend uses `structlog` for JSON-formatted logging:
```python
import structlog
logger = structlog.get_logger(__name__)
logger.info("Operation completed", user_id=123, operation="mint_nft")
```

### Error Handling
- Global exception middleware for unhandled errors
- Custom DRF exception handler for API errors
- React error boundaries for frontend error handling

## 🚀 Deployment

### Production Deployment
1. Update environment variables for production
2. Build production images
3. Deploy using Docker Compose or Kubernetes
4. Configure SSL/TLS certificates
5. Set up monitoring and alerting

### Environment-Specific Configurations
- Development: `infra/.env.dev`
- Production: `infra/.env.prod` (create as needed)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the GitHub repository
- Check the documentation in the `/docs` folder
- Review the health check endpoints for system status

## 🔄 Development Status

### Completed ✅
- [x] Project structure and repository setup
- [x] Django backend with health checks
- [x] React frontend with TypeScript
- [x] Docker Compose development environment
- [x] PostgreSQL and Redis integration
- [x] Structured logging and error handling
- [x] Solana CLI setup scripts

### In Progress 🚧
- [ ] Solana compressed NFT integration
- [ ] Carbon calculation models
- [ ] Sei blockchain migration tools
- [ ] Advanced monitoring and alerting

### Planned 📋
- [ ] Production deployment configuration
- [ ] Comprehensive test suite
- [ ] API documentation
- [ ] User authentication and authorization
- [ ] Advanced carbon credit features