# Architecture Decision Log (ADR)

This log records major technical and architectural decisions made throughout the ClinicQ project.

---

## ADR-001: Multi-Tenancy Strategy — Shared Database with Discriminant Column (`clinic_id`)

- **Status:** Accepted
- **Context:** ClinicQ is a multi-tenant platform designed to support numerous small-to-medium outpatient clinics with rapid onboarding, cost efficiency, and unified migrations.
- **Decision:** Use a single PostgreSQL database with a `clinic_id` foreign key on all tenant-specific tables, combined with repository-level tenant scoping and database foreign key constraints.
- **Consequences:**
  - *Pros:* Simplified migrations, lower operational overhead, rapid tenant onboarding, pooled database connection efficiency.
  - *Mitigations:* Rigorous cross-tenant automated security tests in `tests/security/` run on every PR to verify zero cross-tenant leakage.

---

## ADR-002: Synchronous SQLAlchemy 2.0 with FastAPI

- **Status:** Accepted
- **Context:** FastAPI supports both sync (`def`) and async (`async def`) endpoints. Async database drivers (`asyncpg`) introduce event-loop complexity, thread-local session hazards, and tricky connection pool debugging during concurrent transactions.
- **Decision:** Use synchronous SQLAlchemy 2.0 with standard connection pooling (`psycopg2-binary` or `psycopg3` sync). FastAPI executes standard `def` endpoints in an external threadpool (`starlette.concurrency.run_in_threadpool`), yielding high concurrency without event loop deadlock risks.
- **Consequences:** Clean, readable service and repository code without pervasive `await` syntax; deterministic transaction rollbacks during testing.

---

## ADR-003: Redis Sorted Set (ZSET) for Live Queue with Postgres Source of Truth

- **Status:** Accepted
- **Context:** Walk-in queue ordering needs to handle instant priority reordering (e.g. emergency cases jumping ahead) and high-frequency position lookups.
- **Decision:** PostgreSQL remains the durable source of truth. Redis Sorted Sets (`ZSET`) store the live active queue ordered by score (`priority_weight + arrival_epoch`). An automated rebuild function rebuilds Redis state from PostgreSQL upon startup or Redis connection reset.
- **Consequences:** Blazing fast $O(\log(N))$ queue reads; zero data loss if Redis crashes or is restarted.

---

## ADR-004: Redis Streams for Idempotent Asynchronous Notifications

- **Status:** Accepted
- **Context:** When a patient is 3rd in line, an SMS notification must be dispatched asynchronously without blocking the HTTP request thread, and duplicate sends must never occur on worker retries.
- **Decision:** Use Redis Streams (`XADD`, `XREADGROUP`, `XACK`) for the notification worker pipeline coupled with a PostgreSQL `Notification` table holding a unique `idempotency_key` constraint (`{token_id}:{type}`).
- **Consequences:** Guaranteed at-least-once message delivery from the queue, converted to exactly-once processing via the database unique constraint and worker deduplication check.

---

## ADR-005: UTC Storage for Timestamps with Clinic Timezone Conversion at Edges

- **Status:** Accepted
- **Context:** Clinics operate across diverse local timezones, but datetime arithmetic and slot queries in PostgreSQL must be unambiguous.
- **Decision:** Store all timestamps in UTC (`TIMESTAMP WITH TIME ZONE` in Postgres). Convert to the clinic's local timezone only when formatting display outputs or slot boundaries at the API router layer.
- **Consequences:** Completely eliminates DST transition ambiguities and timezone skew bugs.
