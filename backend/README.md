# Backend

FastAPI backend for Amzur AI Chat.

## Setup

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment variables:

```bash
cp .env.example .env
```

4. Run the API:

```bash
uvicorn app.main:app --reload --port 8000
```

## Architecture

- Routers in app/api
- Business logic in app/services
- ORM models in app/models
- Pydantic schemas in app/schemas
- AI integrations in app/ai
