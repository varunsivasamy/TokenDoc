from fastapi import FastAPI

from app.api.v1.appointments import router as appointments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.doctors import router as doctors_router
from app.api.v1.patients import router as patients_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Application factory for ClinicQ FastAPI instance."""
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Multi-tenant outpatient clinic queue and appointment management system",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    @application.get("/health", tags=["System"])
    def health_check() -> dict[str, str]:
        """Health and liveness check endpoint."""
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    # Mount API Routers
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(doctors_router, prefix="/api/v1")
    application.include_router(patients_router, prefix="/api/v1")
    application.include_router(appointments_router, prefix="/api/v1")

    return application


app = create_app()
