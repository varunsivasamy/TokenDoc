# Design: Health Check Endpoint

## Objective
Provide an unauthenticated, lightweight liveness probe `/health` used by orchestrators (Docker, Kubernetes) and uptime monitors to verify that the FastAPI process is responsive.

## Endpoint Specification
- **Method:** `GET`
- **Path:** `/health`
- **Request Parameters:** None
- **Response Status:** `200 OK`
- **Response Format:**
  ```json
  {
    "status": "ok",
    "app": "ClinicQ",
    "version": "0.1.0"
  }
  ```

## Architecture & SOLID
- **Layer:** `app/main.py` & `app/core/config.py`
- **Single Responsibility (S):** Configuration is read strictly from `Settings` (`app/core/config.py`), while `app/main.py` binds routing and registers health/liveness probes.
