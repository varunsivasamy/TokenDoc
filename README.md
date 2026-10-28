# ClinicQ

> **Enterprise-grade, multi-tenant outpatient clinic queue and appointment management platform featuring atomic token numbering, zero-double-booking concurrency guarantees, real-time Redis priority queues, and dynamic wait-time estimation.**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D.svg)](https://redis.io/)
[![SQLAlchemy 2.0](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![Alembic](https://img.shields.io/badge/Alembic-Migrations-orange.svg)](https://alembic.sqlalchemy.org/)
[![Ruff](https://img.shields.io/badge/Code%20Style-Ruff-black.svg)](https://github.com/astral-sh/ruff)

---

## Table of Contents

- [Overview & The Problem Solved](#overview--the-problem-solved)
- [System Architecture & SOLID Design](#system-architecture--solid-design)
- [Core Engineering Highlights](#core-engineering-highlights)
  - [1. Multi-Tenant Data Isolation](#1-multi-tenant-data-isolation)
  - [2. Zero Double-Booking Concurrency Safety](#2-zero-double-booking-concurrency-safety)
  - [3. Atomic Gap-Free Token Generation](#3-atomic-gap-free-token-generation)
  - [4. Priority-Aware Live Queue (Redis ZSET)](#4-priority-aware-live-queue-redis-zset)
  - [5. Consultation Tracking & Dynamic ETA Calculation](#5-consultation-tracking--dynamic-eta-calculation)
- [Project Structure](#project-structure)
- [Implemented Phases & Feature Status](#implemented-phases--feature-status)
- [API Reference](#api-reference)
- [Database Models & Migrations](#database-models--migrations)
- [Quickstart & Development](#quickstart--development)
- [Running Automated Tests](#running-automated-tests)
- [Roadmap](#roadmap)

---

## Overview & The Problem Solved

Traditional healthcare outpatient departments (OPDs) struggle with severe operational friction:

1. **The Double-Booking Nightmare:** Multiple receptionists or parallel online booking attempts assign two patients to the same doctor slot, causing patient dissatisfaction and clinic chaos.
2. **Crowded, Infectious Waiting Rooms:** Because arrival is based on coarse calendar time slots rather than live doctor speed, patients wait 1 to 2 hours in crowded waiting halls, increasing cross-infection risks.
3. **The Variable Duration Reality:** Medical consultations are inherently non-deterministic—one patient may need 5 minutes while another requires 35 minutes. Fixed static schedules break down within the first hour of clinic operation.
4. **Doctor Idle Time:** When called patients step out for tests or restrooms, doctors wait with empty rooms, degrading clinic throughput.

### The ClinicQ Solution: Hybrid Appointment & Virtual Queueing

ClinicQ combines advance appointment scheduling with day-of-visit **virtual queue tokens** and real-time speed tracking:

- **Advance Booking:** Patients reserve arrival windows, protected against concurrent conflicts by database-level partial unique indexes.
- **Day-of-Visit Tokens:** Walk-ins and pre-booked patients are issued atomic, sequential tokens ($1, 2, 3\dots$) per doctor per day.
- **Just-In-Time Notifications & Tracking:** Patients track the doctor's live progress on mobile phones via anonymous tracking links. An automated proximity alert (e.g., *"You are 3rd in line"*) tells them when to leave home, collapsing waiting room congestion while keeping a 2-patient buffer so the doctor never sits idle.

---

## System Architecture & SOLID Design

ClinicQ enforces a strict, layered architecture with one-way dependency flow:

$$\text{HTTP Routers (FastAPI)} \longrightarrow \text{Business Services} \longrightarrow \text{Tenant Repositories} \longrightarrow \text{PostgreSQL 16 / Redis 7}$$

```
app/
├── api/v1/         # HTTP translation: Pydantic parsing, status codes, route declarations
├── services/       # Domain business logic: Slot generation, booking, state machine, ETA math
├── repositories/   # Storage boundary: Tenant-scoped queries, transactional integrity
├── domain/         # Pure domain rules: Enums, custom exceptions, state machine transitions
├── models/         # SQLAlchemy 2.0 ORM entities with UUID primary keys & tenant foreign keys
└── core/           # Security (JWT, Argon2/bcrypt), configuration, database sessions
```

### Application of SOLID Principles

- **Single Responsibility (SRP):** Routers only parse HTTP requests and return typed Pydantic responses; Services execute pure business workflows; Repositories isolate data persistence.
- **Open/Closed (OCP):** Live queue storage (`LiveQueueStore`) and ETA strategies are defined via abstract protocols, allowing in-memory and Redis implementations without altering service logic.
- **Liskov Substitution (LSP):** Concrete storage implementations (`RedisLiveQueue`, `InMemoryLiveQueue`) and notification adapters conform strictly to shared protocols and pass identical test contracts.
- **Interface Segregation (ISP):** Repositories and domain ports expose minimal, cohesive methods rather than monolithic interfaces.
- **Dependency Inversion (DIP):** Routers and services never instantiate database connections or caching layers directly; all dependencies are injected via FastAPI's `Depends`.

---

## Core Engineering Highlights

### 1. Multi-Tenant Data Isolation

- Every clinic operates as an isolated tenant identified by a unique `clinic_id`.
- The `BaseTenantRepository` automatically binds all queries (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) to the authenticated user's `clinic_id`.
- **Security Verified:** Cross-tenant security tests confirm that users belonging to Clinic A receive `404 Not Found` or empty results when attempting to read or modify records belonging to Clinic B.

### 2. Zero Double-Booking Concurrency Safety

To eliminate double-booking race conditions under high traffic, ClinicQ implements database-level constraint enforcement:

- **Partial Unique Index:**
  ```sql
  CREATE UNIQUE INDEX uq_doctor_slot_active 
  ON appointments (doctor_id, slot_start) 
  WHERE status IN ('BOOKED', 'CONFIRMED');
  ```
- **Stress Tested Under Concurrency:** A dedicated multi-threaded test (`tests/concurrency/test_appointment_concurrency.py`) fires **50 simultaneous booking threads** for the exact same doctor and slot. The system guarantees:
  - Exactly **1 thread succeeds** with `201 Created`.
  - Exactly **49 threads fail** with a structured `409 Conflict` (`SLOT_ALREADY_BOOKED`).
  - Exactly **1 record** exists in the database.

### 3. Atomic Gap-Free Token Generation

Walk-in tokens must be issued sequentially ($1, 2, 3\dots$) per doctor per calendar date without gaps or duplicates:

- **Atomic Sequence Table:** Implemented via `DailyTokenCounter` using atomic database counter increments (`UPDATE ... RETURNING` pattern), completely avoiding dirty reads and `SELECT MAX() + 1` race conditions.
- **Stress Tested Under Concurrency:** `tests/concurrency/test_queue_concurrency.py` fires **100 concurrent token generation requests**. All 100 requests receive consecutive, gap-free numbers ($1$ through $100$) with zero collisions.

### 4. Priority-Aware Live Queue (Redis ZSET)

The active queue is stored in a Redis Sorted Set (`ZSET`) where the float score dictates immediate queue order:

$$\text{Redis ZSET Score Hierarchy}$$

| Rank | State / Category | Score Calculation | Behavior |
|:---:|---|---|---|
| **1** | `IN_CONSULTATION` | `0.0 + (token_number * 0.0001)` | Patient currently in examination room |
| **2** | `CALLED` | `100.0 + (token_number * 0.0001)` | Patient summoned into consultation room |
| **3** | `WAITING` (Emergency) | `1000.0 + (token_number * 0.0001)` | **Leapfrogs to head of waiting queue** |
| **4** | `WAITING` (Appointment Window) | `2000.0 + (token_number * 0.0001)` | Scheduled window priority |
| **5** | `WAITING` (Walk-In) | `5000.0 + token_number` | Standard FIFO arrival order |
| **—** | `COMPLETED` / `NO_SHOW` / `CANCELLED` | `None` | Automatically evicted from active queue |

- **Cold-Start Disaster Recovery:** If Redis restarts, the `/api/v1/queue/doctors/{id}/rebuild` routine reconstructs the entire live queue directly from the PostgreSQL source of truth in milliseconds.

### 5. Consultation Tracking & Dynamic ETA Calculation

Rather than assuming static slot times, ClinicQ measures real doctor throughput:

- **Timestamp Capture:** Transitions into `IN_CONSULTATION` record `consultation_start_at`; completion computes `duration_seconds`.
- **Exponential Moving Average (EMA):**
  $$\text{avg}_{\text{new}} = 0.2 \times \text{duration}_{\text{latest}} + 0.8 \times \text{avg}_{\text{prior}}$$
- **Dynamic Waiting ETA for Position $N$:**
  $$\text{ETA}(N) = \max\left(0, \text{remaining current consultation}\right) + \sum_{i=1}^{N-1} \text{expected\_duration}_i$$
- Yields a realistic wait window (`[eta_min, eta_max]`) displayed on the patient's mobile device.

---

## Project Structure

```
tokendoc/
├── app/
│   ├── main.py                     # FastAPI application factory & router registry
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py             # Login, profile, JWT token generation
│   │       ├── doctors.py          # Doctor profiles, schedules & slot generation
│   │       ├── patients.py         # Patient registration & indexed search
│   │       ├── appointments.py     # Booking, cancellation, rescheduling
│   │       └── queue.py            # Token issuance, call-next, state updates, live queue
│   ├── core/
│   │   ├── config.py               # Pydantic Settings & environment parsing
│   │   ├── database.py             # SQLAlchemy 2.0 Engine & session lifecycle
│   │   ├── dependencies.py         # Multi-tenant context & RBAC guards
│   │   └── security.py             # Password hashing (Argon2/bcrypt) & JWT encoding
│   ├── domain/
│   │   ├── enums.py                # UserRole, AppointmentStatus, QueueStatus
│   │   ├── exceptions.py           # Domain exceptions (InvalidStateTransitionError, etc.)
│   │   ├── ports.py                # Protocol definitions (LiveQueueStore, SmsSender)
│   │   └── state_machine.py        # Token lifecycle legal transitions validator
│   ├── models/
│   │   ├── base.py                 # Declarative Base, UUIDPrimaryKeyMixin, TimestampMixin
│   │   ├── clinic.py               # Clinic tenant model
│   │   ├── user.py                 # User model with role enumeration
│   │   ├── doctor.py               # Doctor entity
│   │   ├── doctor_schedule.py      # Weekly recurring doctor shift schedules
│   │   ├── patient.py              # Patient entity with MRN & clinic-scoped phone
│   │   ├── appointment.py          # Appointment with partial unique index
│   │   ├── queue_token.py          # Queue token & DailyTokenCounter entities
│   │   └── consultation.py         # Consultation record & DoctorEtaProfile (EMA)
│   ├── repositories/
│   │   ├── base_repository.py      # Generic tenant-scoped repository
│   │   ├── appointment_repository.py
│   │   ├── consultation_repository.py
│   │   ├── doctor_repository.py
│   │   ├── patient_repository.py
│   │   ├── schedule_repository.py
│   │   ├── token_repository.py
│   │   └── user_repository.py
│   ├── schemas/                    # Pydantic v2 validation & serialization schemas
│   └── services/
│       ├── auth_service.py         # Credential validation & token generation
│       ├── booking_service.py      # Double-booking-safe appointment manager
│       ├── doctor_service.py       # Doctor entity management
│       ├── live_queue.py           # Redis & in-memory priority queue engine
│       ├── patient_service.py      # Patient creation & search
│       ├── queue_service.py        # Token issuing, calling, and state transitions
│       └── slot_service.py         # Dynamic schedule slot generation
├── docs/
│   ├── decisions.md                # Architectural Decision Records (ADRs)
│   ├── requirements.md             # Functional requirements & acceptance criteria
│   └── design/                     # Architectural design specifications
├── migrations/
│   ├── env.py                      # Alembic migration environment
│   └── versions/
│       ├── 0001_clinic_and_user.py
│       ├── 0002_doctor_and_patient.py
│       ├── 0003_appointment_unique_index.py
│       ├── 0004_queue_token_and_counter.py
│       └── 0005_consultation_and_eta_profile.py
├── tests/
│   ├── concurrency/                # Multi-threaded race condition tests (50–100 threads)
│   ├── integration/                # End-to-end API workflows with real database
│   ├── security/                   # Cross-tenant data isolation tests
│   └── unit/                       # State machine, slot math, priority scoring unit tests
├── docker-compose.yml              # PostgreSQL 16 & Redis 7 services
├── pyproject.toml                  # Dependencies & tool configurations
└── README.md
```

---

## Implemented Phases & Feature Status

| Phase | Milestone | Core Deliverables | Status |
|:---:|---|---|:---:|
| **Phase 0** | Project Setup & Tooling | Docker Compose, FastAPI factory, Ruff linter, Pytest testbed, `/health` endpoint | **Done** |
| **Phase 1** | Multi-Tenancy & Auth | Tenant-isolated base repository, Argon2/bcrypt hashing, JWT tokens, RBAC dependencies | **Done** |
| **Phase 2** | Doctors & Patients | Doctor registries, recurring schedules, patient directory with MRN and fast search | **Done** |
| **Phase 3** | Appointments & Anti-Double-Booking | Dynamic slot generation, partial unique indexes, 50-thread concurrency validation | **Done** |
| **Phase 4** | Queue State Machine & Live Queue | Atomic daily token generation, strict queue transitions, Redis ZSET priority engine | **Done** |
| **Phase 5** | Consultations & Moving Average ETA | Consultation start/end duration capture, Exponential Moving Average pace tracking | **Done** |
| **Phase 6** | Live SSE & Public Status Board | Server-Sent Events live feed, unguessable mobile tracking URL (`tk_...`) | *Roadmap* |
| **Phase 7** | Idempotent Notification Pipeline | Worker queue, Redis streams, automated proximity SMS ("3rd in line") | *Roadmap* |
| **Phase 8** | Digital Prescriptions & Billing | Medical prescription items, line-item decimal billing and invoice generation | *Roadmap* |
| **Phase 9** | Audit Trail & Hardening | Structured JSON audit logs, rate limiting, and security compliance | *Roadmap* |

---

## API Reference

### System & Health
| Method | Path | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/health` | Public | System health and liveness check |

### Authentication & Users
| Method | Path | Auth / Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Public | Authenticate email/password; returns JWT access token |
| `GET` | `/api/v1/auth/me` | Authenticated | Retrieve current user profile and clinic tenant ID |
| `GET` | `/api/v1/auth/users` | Clinic Admin | List all staff accounts belonging to current clinic |

### Doctors & Schedules
| Method | Path | Auth / Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/doctors` | Clinic Admin | Register a doctor with specialty and default slot duration |
| `GET` | `/api/v1/doctors` | Authenticated | List all active doctors in authenticated clinic |
| `GET` | `/api/v1/doctors/{id}` | Authenticated | Get doctor details by ID |
| `POST` | `/api/v1/doctors/{id}/schedules` | Clinic Admin | Create recurring weekly shift schedule |
| `GET` | `/api/v1/doctors/{id}/slots` | Authenticated | Compute available appointment slots for a given date |

### Patients
| Method | Path | Auth / Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/patients` | Staff | Register a patient (validates phone uniqueness per clinic) |
| `GET` | `/api/v1/patients/search` | Staff | Search patients by name, phone, or MRN with pagination |
| `GET` | `/api/v1/patients/{id}` | Staff | Retrieve patient profile by ID |

### Appointments
| Method | Path | Auth / Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/appointments` | Staff | Book an appointment (atomic check; returns `409 Conflict` if taken) |
| `GET` | `/api/v1/appointments/{id}` | Staff | Retrieve appointment details |
| `POST` | `/api/v1/appointments/{id}/cancel` | Staff | Cancel an appointment and immediately release the slot |
| `POST` | `/api/v1/appointments/{id}/reschedule` | Staff | Atomically reschedule to a new available slot |

### Live Queue Management
| Method | Path | Auth / Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/queue/tokens` | Staff | Issue an atomic, sequential walk-in or appointment token |
| `POST` | `/api/v1/queue/doctors/{id}/call-next` | Doctor / Staff | Call the next patient in priority order |
| `PATCH` | `/api/v1/queue/tokens/{id}/status` | Doctor / Staff | Transition token state (`WAITING` $\to$ `CALLED` $\to$ `IN_CONSULTATION` $\to$ `COMPLETED`) |
| `POST` | `/api/v1/queue/tokens/{id}/no-show` | Doctor / Staff | Mark a called patient as `NO_SHOW` on arrival timeout |
| `GET` | `/api/v1/queue/doctors/{id}` | Doctor / Staff | Retrieve live active queue ordered by priority |
| `POST` | `/api/v1/queue/doctors/{id}/rebuild` | Staff | Rebuild Redis live queue from PostgreSQL source of truth |

---

## Database Models & Migrations

Database evolution is managed via structured Alembic migration revisions:

```
0001_clinic_and_user
  ├── clinics (id, name, slug)
  └── users (id, clinic_id, email, hashed_password, role, is_active)
        └── 0002_doctor_and_patient
              ├── doctors (id, clinic_id, full_name, specialty, room_number, default_slot_duration_minutes)
              ├── doctor_schedules (id, clinic_id, doctor_id, day_of_week, start_time, end_time)
              └── patients (id, clinic_id, full_name, phone, medical_record_number)
                    └── 0003_appointment_unique_index
                          └── appointments (id, clinic_id, doctor_id, patient_id, slot_start, slot_end, status)
                                [INDEX: uq_doctor_slot_active ON (doctor_id, slot_start)]
                                └── 0004_queue_token_and_counter
                                      ├── daily_token_counters (id, clinic_id, doctor_id, token_date, last_number)
                                      └── queue_tokens (id, clinic_id, doctor_id, patient_id, token_number, token_date, access_code, status, is_emergency)
                                            └── 0005_consultation_and_eta_profile
                                                  ├── consultations (id, clinic_id, doctor_id, patient_id, token_id, started_at, ended_at, duration_seconds)
                                                  └── doctor_eta_profiles (doctor_id, clinic_id, current_avg_seconds, consultation_count)
```

---

## Quickstart & Development

### 1. Prerequisites
- **Python:** 3.12 or newer
- **Container Runtime:** Docker & Docker Compose

### 2. Clone & Environment Setup
```bash
# Clone the repository
git clone https://github.com/your-org/clinicq.git
cd clinicq

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies in editable mode
pip install -e ".[dev]"

# Create local environment file
cp .env.example .env
```

### 3. Start Database and Cache
```bash
docker compose up -d
```
This starts:
- **PostgreSQL 16** on `localhost:5432`
- **Redis 7** on `localhost:6379`

### 4. Run Database Migrations
```bash
alembic upgrade head
```

### 5. Start the FastAPI Development Server
```bash
uvicorn app.main:app --reload --port 8000
```

- Interactive OpenAPI Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Interactive ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

---

## Running Automated Tests

The test suite covers unit, integration, cross-tenant security, and high-concurrency race conditions:

```bash
# Run all tests
pytest -v

# Run concurrency tests only
pytest tests/concurrency/ -v

# Run cross-tenant security tests only
pytest tests/security/ -v

# Run code style & lint checks
ruff check .
ruff format --check .
```

---

## Roadmap

- [x] **Phases 0–5:** Core, Multi-Tenancy, Appointments, Queue State Machine, Atomic Tokens, Real-time Priority Sorting, Consultations & Moving Average Wait Times.
- [ ] **Phase 6:** Server-Sent Events (SSE) live waiting room screen feed and privacy-preserving public patient QR tracker.
- [ ] **Phase 7:** Idempotent notification worker pipeline using Redis Streams with automated "3rd in line" SMS alerts.
- [ ] **Phase 8:** Prescription authoring and decimal billing / invoice calculations.
- [ ] **Phase 9:** Structured security audit trail and compliance hardening.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
