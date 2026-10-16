from fastapi import FastAPI

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

    return application


app = create_app()
