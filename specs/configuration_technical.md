# specs/configuration_technical.md
# Configuration & Documentation Specifications

## Environment Variables Requirements

### Security Requirements
- Sensitive values MUST NOT be committed to git
- All secrets must use environment variables
- Default values must be safe for development
- Production values must be injected at runtime

### Required Variables by Component

#### Core Application
- `LOG_LEVEL`: Log verbosity (DEBUG, INFO, WARNING, ERROR)
- `ENVIRONMENT`: Deployment environment (development, staging, production)
- `SECRET_KEY`: Cryptographically secure secret key

#### Database
- `DATABASE_URL`: PostgreSQL connection string
- `DATABASE_POOL_SIZE`: Connection pool size
- `DATABASE_MAX_OVERFLOW`: Maximum overflow connections

#### External Services
- `OPENCLAW_API_KEY`: OpenClaw network API key
- `OPENCLAW_ENDPOINT`: OpenClaw API endpoint
- `TENX_MCP_SENSE_KEY`: Tenx MCP Sense API key
- `YOUTUBE_API_KEY`: YouTube Data API key

#### Agent Configuration
- `AGENT_CONCURRENCY_LIMIT`: Maximum concurrent agents
- `AGENT_TIMEOUT_SECONDS`: Agent execution timeout
- `SKILL_RETRY_ATTEMPTS`: Skill execution retry attempts

## Dependencies Management Requirements

### uv Requirements
- Must use uv for Python dependency management
- Must have separate dependency groups:
  - `base`: Core runtime dependencies
  - `dev`: Development tools
  - `test`: Testing frameworks
  - `prod`: Production-only dependencies
- Must lock dependencies for reproducibility

### Security Scanning
- Dependencies must be scanned for vulnerabilities
- Regular updates must be enforced
- Pinned versions must be used in production

## Documentation Requirements

### README.md Must Include
- Project overview and business objective
- Quick start guide
- Architecture diagram
- API documentation link
- Development setup instructions
- Deployment instructions
- Contributing guidelines

### SECURITY.md Must Include
- Security policy and reporting process
- Known vulnerabilities
- Security best practices
- Encryption standards
- Audit logging requirements

## Pre-commit Requirements

### Must Enforce
- Code formatting (Black)
- Import sorting (isort)
- Linting (Flake8)
- Type checking (mypy)
- Security scanning (Bandit)
- Commit message validation

## Git Operations Requirements

### .gitignore Must Exclude
- Environment-specific files
- Build artifacts
- Dependency caches
- IDE configuration
- Sensitive data files
- Local development files

### Commit Messages Must Follow
- Conventional Commits specification
- Reference to spec or issue number
- Clear description of changes