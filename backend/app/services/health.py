from app.core.config import Settings
from app.schemas.health import HealthResponse


def get_health_status(settings: Settings) -> HealthResponse:
    """Report that the API process is up.

    Later phases can extend this with dependency checks (database, Gemini).
    """
    return HealthResponse(status="ok", service=settings.app_name)
