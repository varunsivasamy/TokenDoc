# Design: Authentication & Login Endpoint

## Objective
Provide a secure login endpoint `POST /api/v1/auth/login` allowing clinic staff to authenticate using email and password, receiving a signed JWT containing user identity, clinic ID, and role.

## Endpoint Specification
- **Method:** `POST`
- **Path:** `/api/v1/auth/login`
- **Request Body:**
  ```json
  {
    "email": "doctor@apexclinic.com",
    "password": "Password123!"
  }
  ```
- **Responses:**
  - `200 OK`:
    ```json
    {
      "access_token": "eyJhbGciOi...",
      "token_type": "bearer",
      "user": {
        "id": "uuid",
        "email": "doctor@apexclinic.com",
        "full_name": "Dr. Sarah Adams",
        "role": "DOCTOR",
        "clinic_id": "clinic-uuid"
      }
    }
    ```
  - `401 Unauthorized`: For nonexistent user, deactivated user, or invalid password.

## Layered Architecture (SOLID)
- **Router:** `app/api/v1/auth.py` (receives HTTP payload, calls AuthService)
- **Service:** `app/services/auth_service.py` (verifies password via Security, builds JWT)
- **Repository:** `app/repositories/user_repository.py` (retrieves User entity from database)
- **Dependency Inversion:** AuthService depends on UserRepository protocol/abstraction.
