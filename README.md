# ClinicQ

> Multi-tenant outpatient clinic queue and appointment management system with real-time updates and idempotent notifications.

---

## Architecture & SOLID Design

ClinicQ follows a clean, layered architectural pattern:

$$\text{Router (HTTP)} \longrightarrow \text{Service (Business Rules)} \longrightarrow \text{Repository (Data Access)}$$

- **S (Single Responsibility):** Routers handle HTTP parsing and responses; Services encapsulate core business rules; Repositories isolate database interactions.
- **O (Open/Closed):** Extensible strategies (e.g. `EtaStrategy`) allow adding new behaviors without modifying existing logic.
- **L (Liskov Substitution):** Notification senders (`ConsoleSender`, `FakeSender`, `TwilioSender`) conform strictly to the `SmsSender` protocol.
- **I (Interface Segregation):** Small, cohesive protocols prevent bloated interfaces.
- **D (Dependency Inversion):** Services depend on abstractions injected via FastAPI `Depends`, never concrete implementations.

---

## Tech Stack

- **Runtime & Framework:** Python 3.12+, FastAPI, Pydantic v2
- **Database & ORM:** PostgreSQL 16, SQLAlchemy 2.0 (Sync), Alembic
- **Caching & Job Queue:** Redis 7 (Redis Streams, Sorted Sets)
- **Tooling & Quality:** Ruff, Pytest, Docker Compose, Pre-commit, GitHub Actions CI

---

## Project Structure

```
clinicq/
├── app/
│   ├── main.py              # Application entrypoint
│   ├── core/                # Settings, security, database session
│   ├── domain/              # Enums, interfaces (protocols), exceptions
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── repositories/        # Database access layer
│   ├── services/            # Business logic layer
│   ├── api/v1/              # Versioned API routers
│   └── workers/             # Notification and background job workers
├── migrations/              # Alembic database migrations
├── tests/
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests with real DB
│   ├── concurrency/         # Concurrency and race condition tests
│   └── security/            # Cross-tenant isolation and auth tests
├── frontend/                # React + Vite (Phases 6+)
├── docs/                    # Requirements, design notes, decision log
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quickstart

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.12+

### 2. Environment Setup
```bash
cp .env.example .env
```

### 3. Start Infrastructure
```bash
docker compose up -d
```

### 4. Run the API Server
```bash
# In virtualenv
uvicorn app.main:app --reload --port 8000
```

Verify health:
```bash
curl http://localhost:8000/health
```

---

## Development & Testing

```bash
# Run linting
ruff check .
ruff format --check .

# Run test suite
pytest
```

---

## Playbook Phases

- [x] **Phase 0:** Project setup, requirements, CI, Docker Compose, Health endpoint
- [ ] **Phase 1:** Core, multi-tenant database, authentication, and RBAC (`v0.1.0`)
- [ ] **Phase 2:** Doctors and patients with tenant isolation (`v0.2.0`)
- [ ] **Phase 3:** Appointments & double-booking prevention (`v0.3.0`)
- [ ] **Phase 4:** Queue state machine and atomic token numbering (`v0.4.0`)
- [ ] **Phase 5:** Consultations & moving average ETA calculation (`v0.5.0`)
- [ ] **Phase 6:** Live SSE updates and public status board (`v0.6.0`)
- [ ] **Phase 7:** Idempotent notification worker pipeline (`v0.7.0`)
- [ ] **Phase 8:** Prescriptions and decimal billing (`v0.8.0`)
- [ ] **Phase 9:** Audit logging, security hardening, final documentation (`v1.0.0`)
