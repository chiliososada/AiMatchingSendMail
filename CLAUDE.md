# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AiMatchingSendMail is a multi-tenant email sending API system with AI-powered matching capabilities for job recruitment. Built with FastAPI, it combines traditional email services with AI matching between projects and engineers/resumes.

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Generate encryption keys
python generate_keys.py
```

### Docker Development
```bash
# Start all services
docker-compose up -d

# Start with database admin tools
docker-compose --profile admin up -d

# View logs
docker-compose logs -f email-api

# Stop services
docker-compose down
```

### Testing
```bash
# Run unit tests
pytest

# Run specific test file
pytest tests/test_email_service.py

# Test AI matching functionality
python test_ai_matching.py

# Debug extractors
python debug_extractors.py
```

### Database Operations
```bash
# Initialize AI matching database
python init_ai_matching_db.py

# Check table structure
python check_tables.py

# Generate embeddings for AI matching
python generate_embeddings.py
```

## Architecture Overview

### Core Application Structure (`/app/`)
- **main.py**: FastAPI application entry point with middleware setup
- **config.py**: Pydantic-based settings management with environment validation
- **database.py**: AsyncPG connection pool management for high-performance database operations

### API Layer (`/app/api/`)
- **email_routes.py**: Email sending, SMTP management, and queue operations
- **smtp_routes.py**: SMTP configuration and password decryption services
- **ai_matching_routes.py**: AI-powered project-to-engineer matching endpoints
- **resume_parser_routes.py**: Resume parsing and data extraction services
- **diagnostic_routes.py**: System diagnostics and health monitoring

### Services Layer (`/app/services/`)
- **email_service.py**: Core email sending logic with queue management
- **smtp_service.py**: SMTP configuration with Fernet encryption
- **ai_matching_service.py**: AI matching algorithms using sentence-transformers
- **ai_matching_database.py**: AI matching database operations with pgvector
- **resume_parser_service.py**: Resume parsing orchestration

### Data Extraction (`/app/services/extractors/`)
Specialized extractors for resume parsing:
- Base class: `base_extractor.py`
- Extractors: name, skills, experience, nationality, Japanese level, age, gender, role, work scope, arrival year

### Database Models (`/app/models/`)
- **email_models.py**: Database models for email operations using AsyncPG

### Utilities (`/app/utils/`)
- **security.py**: Fernet encryption/decryption for SMTP passwords
- **date_utils.py**: Date parsing with multiple format support
- **text_utils.py**: Text processing and cleaning utilities
- **validation_utils.py**: Data validation helpers

## Key Technologies

### Backend Stack
- **FastAPI**: High-performance async web framework
- **AsyncPG**: High-performance PostgreSQL driver with connection pooling
- **Pydantic**: Data validation and settings management

### Database
- **PostgreSQL 15+** with **pgvector** extension for AI embeddings
- Connection pooling for high concurrency

### AI/ML Components
- **sentence-transformers**: Text embedding generation for matching
- **torch**: Deep learning framework
- **numpy**: Numerical computing

### Email Services
- **aiosmtplib**: Async SMTP client
- **cryptography**: Fernet encryption for SMTP passwords

## Configuration

### Environment Setup
1. Copy `.env.example` to `.env`
2. Generate encryption keys: `python generate_keys.py`
3. Set database URL and other required environment variables
4. Configure SMTP settings for email sending

### Key Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Application secret key
- `ENCRYPTION_KEY`: Fernet key for SMTP password encryption
- `MAX_FILE_SIZE`: File upload size limit (default 25MB)
- `MAX_RECIPIENTS_PER_EMAIL`: Email recipient limit (default 100)

## Multi-Tenant Architecture

The system is designed for multi-tenant operation:
- Each tenant has isolated SMTP configurations
- Database operations are tenant-scoped
- File uploads are organized by tenant
- AI matching operates within tenant boundaries

## AI Matching System

### Setup
1. Initialize database: `python init_ai_matching_db.py`
2. Generate embeddings: `python generate_embeddings.py`

### Components
- **Vector similarity search** using pgvector for PostgreSQL
- **Sentence transformers** for text embedding generation
- **Bulk matching capabilities** for large datasets
- **Debugging tools** for matching algorithm analysis

## File Structure Patterns

### Upload Organization
```
uploads/
├── attachments/     # Email attachments
├── temp/           # Temporary files
└── temp/resumes/   # Resume processing temp files
```

### Service Layer Pattern
Each service follows the pattern:
1. Input validation using Pydantic schemas
2. Business logic implementation
3. Database operations via AsyncPG
4. Error handling and logging
5. Response formatting

## Security Features

- **Fernet encryption** for SMTP passwords (compatible with aimachingmail project)
- **Multi-tenant data isolation**
- **File type validation** with security checks
- **Rate limiting** and request size limits
- **CORS configuration** for frontend integration

## Integration Notes

### SMTP Service Integration
Compatible with aimachingmail project for SMTP configuration sharing:
```python
# Get decrypted SMTP config
GET /api/v1/smtp/config/{tenant_id}/default
```

### React Native Integration
See `examples/react-native-example.js` for mobile integration patterns.

## Common Development Tasks

### Adding New Email Features
1. Define schema in `schemas/email_schemas.py`
2. Implement service logic in `services/email_service.py`
3. Add API endpoint in `api/email_routes.py`
4. Add database model if needed in `models/email_models.py`

### Adding Resume Extractors
1. Create extractor class extending `base/base_extractor.py`
2. Implement extraction logic using regex/ML patterns
3. Add to extraction pipeline in `resume_parser_service.py`
4. Test with `debug_extractors.py`

### Database Schema Changes
1. Update models in `models/`
2. Consider data migration needs
3. Update `init_ai_matching_db.py` if adding AI-related tables
4. Test with `check_tables.py`

## Performance Considerations

- AsyncPG connection pooling supports 1000+ concurrent connections
- AI embeddings are cached for performance
- File uploads have automatic cleanup routines
- Database queries are optimized for multi-tenant scenarios
- Use bulk operations for large datasets