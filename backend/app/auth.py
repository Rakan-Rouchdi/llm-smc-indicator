import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import Settings, get_settings


DEVELOPMENT_ENVIRONMENTS = {"development", "dev", "local", "test"}
dashboard_basic = HTTPBasic(auto_error=False)


def require_dashboard_auth(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(dashboard_basic)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    username = settings.dashboard_username
    password = (
        settings.dashboard_password.get_secret_value()
        if settings.dashboard_password is not None
        else None
    )

    if not username and not password:
        if settings.app_env.strip().lower() in DEVELOPMENT_ENVIRONMENTS:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard authentication is not configured",
        )

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard authentication is incomplete",
        )

    authenticated = (
        credentials is not None
        and secrets.compare_digest(
            credentials.username.encode("utf-8"),
            username.encode("utf-8"),
        )
        and secrets.compare_digest(
            credentials.password.encode("utf-8"),
            password.encode("utf-8"),
        )
    )
    if not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid dashboard credentials",
            headers={"WWW-Authenticate": 'Basic realm="SMC LLM Dashboard"'},
        )
