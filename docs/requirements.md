# ClinicQ Requirements & Acceptance Criteria

This document details the user roles, user stories, and acceptance criteria for all phases of ClinicQ, following strict SDLC and SOLID design principles.

---

## 1. User Roles & Permissions

| Role | Scope | Description & Capabilities |
|---|---|---|
| **Super Admin** | System-wide | Platform-level administrator managing clinics and global configurations. |
| **Clinic Admin** | Clinic-scoped | Manages clinic metadata, doctors, clinic staff accounts, and clinic-wide settings. |
| **Doctor** | Clinic-scoped | Manages personal schedules, views queue, calls patients, conducts consultations, writes prescriptions. |
| **Receptionist** | Clinic-scoped | Registers patients, issues walk-in queue tokens, books/reschedules appointments, manages billing/invoices. |
| **Patient (Public)** | Anonymous / Token Code | Accesses live queue status and estimated wait time via an unguessable token code; no login required, no PII exposed. |

---

## 2. Feature Requirements by Phase

### Phase 1: Core, Authentication & Multi-Tenancy

#### Story 1.1: Multi-Tenant Tenant Isolation
- **As a** Clinic User (Admin, Doctor, Receptionist)
- **I want** all my data operations automatically restricted to my clinic
- **So that** data from Clinic A can never be accessed or modified by Clinic B.
- **Acceptance Criteria:**
  1. Every database query in tenant-scoped repositories filters by `clinic_id`.
  2. A user authenticating from Clinic A attempting to access an entity belonging to Clinic B receives `404 Not Found` (or `403 Forbidden`).
  3. Base repository enforces tenant filtering by default on all select, update, and delete statements.

#### Story 1.2: Authentication & Role-Based Access Control (RBAC)
- **As a** Clinic Staff Member
- **I want** to securely log in using email and password to receive a JWT access token
- **So that** only authorized users can access role-protected endpoints.
- **Acceptance Criteria:**
  1. `POST /api/v1/auth/login` accepts email and password.
  2. Passwords are encrypted using modern hashing (Argon2 / bcrypt via Passlib/pwdlib).
  3. Returns a signed JWT containing `sub` (user_id), `clinic_id`, and `role`.
  4. Invalid credentials return `401 Unauthorized` with generic error text.
  5. Endpoints protected with `require_role(...)` enforce role restrictions and reject unauthorized roles with `403 Forbidden`.

---

### Phase 2: Doctors & Patients

#### Story 2.1: Doctor Registry Management
- **As a** Clinic Admin
- **I want** to register and manage doctors within my clinic
- **So that** appointments and queue slots can be scheduled under them.
- **Acceptance Criteria:**
  1. `POST /api/v1/doctors` creates a doctor record with specialty, consultation room, and default slot duration.
  2. `GET /api/v1/doctors` returns a list of active doctors for the authenticated clinic only.
  3. Only `Clinic Admin` role can create or update doctor records.

#### Story 2.2: Patient Registration & Search
- **As a** Receptionist
- **I want** to register new patients and quickly search existing patients by name or phone number
- **So that** check-in is quick and duplicate records are prevented.
- **Acceptance Criteria:**
  1. `POST /api/v1/patients` creates a patient record with full name, phone number, DOB, and medical record number.
  2. Duplicate phone numbers within the same clinic are rejected with `409 Conflict`.
  3. `GET /api/v1/patients/search?q={query}` returns paginated matches (`limit`, `offset`) filtered by clinic.
  4. Cross-tenant search queries return zero results for patients belonging to other clinics.

---

### Phase 3: Appointments & Double-Booking Prevention

#### Story 3.1: Doctor Schedule & Slot Generation
- **As a** Receptionist or Patient
- **I want** to view available time slots for a doctor on a specific date
- **So that** I can book a consultation at an open time.
- **Acceptance Criteria:**
  1. `GET /api/v1/doctors/{id}/slots?date=YYYY-MM-DD` returns available slots in UTC.
  2. Slots are generated based on the doctor's working schedule and slot duration.
  3. Already booked active slots are excluded from the available list.

#### Story 3.2: Concurrent Booking with Zero Double-Booking
- **As a** Clinic Administrator
- **I want** absolute prevention of double-booking even under extreme concurrent requests
- **So that** two patients never get assigned the same doctor slot.
- **Acceptance Criteria:**
  1. Database enforces a partial unique index on `(doctor_id, slot_start)` where `status IN ('BOOKED', 'CONFIRMED')`.
  2. Concurrency test with 50 parallel booking requests for the same slot yields exactly 1 success (`201 Created`) and 49 conflicts (`409 Conflict`).
  3. The service catches the database integrity violation and translates it into a structured `409 Conflict` response with error code `SLOT_ALREADY_BOOKED`.

#### Story 3.3: Cancellation & Rescheduling
- **As a** Receptionist
- **I want** to cancel or reschedule an existing appointment
- **So that** freed slots immediately become available for other patients.
- **Acceptance Criteria:**
  1. `POST /api/v1/appointments/{id}/cancel` marks the appointment as `CANCELLED`.
  2. The unique index allows a new booking for the same slot once the previous is cancelled.

---

### Phase 4: Queue State Machine & Atomic Token Numbering

#### Story 4.1: Atomic Walk-In Token Generation
- **As a** Receptionist
- **I want** to generate walk-in queue tokens with guaranteed unique, gap-free numbers per doctor per day
- **So that** patients have a deterministic, fair queue number.
- **Acceptance Criteria:**
  1. Tokens are numbered sequentially (`1, 2, 3, ...`) per doctor per calendar date.
  2. Atomic generation uses Postgres `UPDATE ... RETURNING` or Redis atomic increment (`INCR`).
  3. Never uses `SELECT MAX() + 1`.
  4. 100 parallel token generation requests result in 100 consecutive numbers without duplicates or gaps.

#### Story 4.2: Queue State Machine
- **As a** Doctor or Receptionist
- **I want** the queue token lifecycle strictly enforced by a state machine
- **So that** invalid state transitions are rejected.
- **Acceptance Criteria:**
  1. Legal transitions:
     - `WAITING` $\rightarrow$ `CALLED`
     - `CALLED` $\rightarrow$ `IN_CONSULTATION`
     - `CALLED` $\rightarrow$ `NO_SHOW`
     - `IN_CONSULTATION` $\rightarrow$ `COMPLETED`
     - Any non-final state $\rightarrow$ `CANCELLED`
  2. Any transition outside the allowed transition matrix returns `422 Unprocessable Entity` with details of the invalid transition.

#### Story 4.3: Real-Time Live Queue Ordering & Recovery
- **As a** Doctor
- **I want** to view the live queue ordered by priority and arrival time
- **So that** emergency cases and scheduled appointment windows take precedence.
- **Acceptance Criteria:**
  1. Live queue maintained in Redis Sorted Set (ZSET) ordered by calculated priority score.
  2. Startup recovery procedure rebuilds Redis ZSET directly from Postgres truth on startup.
  3. Emergency tokens bypass normal queue order to the front of `WAITING` status.

---

### Phase 5: Consultations & Moving Average Wait-Time ETA

#### Story 5.1: Consultation Duration Tracking
- **As a** Clinic Manager
- **I want** accurate tracking of consultation start times, end times, and duration
- **So that** real wait times can be modeled historically.
- **Acceptance Criteria:**
  1. Transition into `IN_CONSULTATION` records `consultation_start_time`.
  2. Transition to `COMPLETED` records `consultation_end_time` and computes duration in seconds.

#### Story 5.2: Exponential Moving Average Wait-Time Estimation
- **As a** Patient in the queue
- **I want** to see an estimated wait time range based on the doctor's actual pace today
- **So that** I know when to return to the waiting area.
- **Acceptance Criteria:**
  1. Doctor's average consultation duration updated via moving average:
     $$\text{new\_avg} = 0.2 \times \text{latest\_duration} + 0.8 \times \text{old\_avg}$$
  2. Initial doctor default seed: 10 minutes (600 seconds).
  3. Total ETA for position $N$ equals:
     $$\text{ETA} = \max(0, \text{remaining current consultation}) + \sum_{i=1}^{N-1} \text{expected duration}_i$$
  4. Response returns a range: `[eta_min, eta_max]` in minutes.
  5. Edge cases handled cleanly: empty queue returns 0 minutes; consultation running overtime never yields negative remaining time.

---

### Phase 6: Live Updates & Public Status Board

#### Story 6.1: Server-Sent Events (SSE) Live Queue Feed
- **As a** Receptionist or Patient
- **I want** real-time queue updates without manually refreshing the browser
- **So that** changes appear within 1 second.
- **Acceptance Criteria:**
  1. Queue state changes publish an event to Redis Pub/Sub channel `clinic:{clinic_id}:doctor:{doctor_id}:queue`.
  2. `GET /api/v1/queue/doctors/{id}/stream` streams SSE events (`text/event-stream`).

#### Story 6.2: Privacy-Preserving Public Patient Status
- **As a** Patient with a token ticket
- **I want** to track my token's live status via a QR code / short URL on my phone
- **So that** I can wait outside the clinic safely without logging in.
- **Acceptance Criteria:**
  1. Each token is issued an unguessable random alphanumeric access code (e.g. `tk_9f8b2c1a`).
  2. `GET /api/v1/public/tokens/{access_code}` returns: token number, current status, queue position, and ETA range.
  3. Response contains **zero PII** (no patient name, phone, or medical notes).

---

### Phase 7: Idempotent Notification Pipeline

#### Story 7.1: Pluggable SMS Sender Interface (Liskov Substitution)
- **As a** Developer
- **I want** notification senders defined via a small `SmsSender` protocol
- **So that** test runners use `FakeSender`, local dev uses `ConsoleSender`, and production uses `TwilioSender` without modifying any service code.
- **Acceptance Criteria:**
  1. `SmsSender` protocol defines `send(to: str, text: str) -> None`.
  2. Contract tests verify identical error and success semantics across all implementations.

#### Story 7.2: Idempotent Job Queue & Dead-Letter Handling
- **As a** System Architect
- **I want** SMS notifications (e.g., "You are 3rd in line") delivered reliably without duplicates
- **So that** patients never receive repeated alerts if workers restart.
- **Acceptance Criteria:**
  1. Database `Notification` record enforces a unique `idempotency_key` (e.g. `{token_id}:{notification_type}`).
  2. Worker processes jobs from Redis Streams with automatic ACK.
  3. Repeated message events detect existing key and skip sending.
  4. Failed deliveries undergo exponential backoff with jitter (up to 3 retries).
  5. Permanent failures are stored in a Dead Letter Queue / table with error cause.

---

### Phase 8: Prescriptions & Decimal Billing

#### Story 8.1: Doctor Prescriptions
- **As a** Doctor
- **I want** to write digital prescriptions with line items (medication, dosage, instructions)
- **So that** the patient and pharmacy have an accurate clinical record.
- **Acceptance Criteria:**
  1. Only doctors can create prescriptions for patients linked to their consultations.
  2. Items validated for positive dosage quantities.

#### Story 8.2: Accurate Financial Billing with Idempotency
- **As a** Receptionist
- **I want** to generate invoices and collect payments with strict decimal precision
- **So that** rounding errors and duplicate card charges never occur.
- **Acceptance Criteria:**
  1. All currency calculations use Python `Decimal` and PostgreSQL `NUMERIC(12, 2)`. Floats are strictly prohibited.
  2. `POST /api/v1/billing/invoices/{id}/pay` requires an `Idempotency-Key` header.
  3. Retried payment calls with the same key return the recorded payment result without charging twice.

---

### Phase 9: Audit Logging, Security Hardening & Observability

#### Story 9.1: Comprehensive Write Audit Log
- **As a** Compliance Officer
- **I want** every write, update, and delete to be recorded with actor, action, timestamp, and diff
- **So that** all clinical and financial activity is auditable.
- **Acceptance Criteria:**
  1. `AuditLog` captures `actor_user_id`, `clinic_id`, `action`, `resource_type`, `resource_id`, and `changes_diff` (JSON).

#### Story 9.2: Rate Limiting & Error Standardization
- **As a** Security Engineer
- **I want** rate limiting on authentication and uniform error responses
- **So that** brute-force attacks are mitigated and clients receive consistent error payloads.
- **Acceptance Criteria:**
  1. Login endpoint rate-limited to 5 attempts per minute per IP.
  2. Global exception handlers catch unhandled exceptions and return uniform JSON: `{"error": {"code": str, "message": str, "details": any}}`.
