"""API token authentication."""

import logging

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def verify_token(
    authorization: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """Verify the API token.

    Skips validation when ``API_TOKEN`` is not configured (empty string).
    Returns the token on success, raises 403 on mismatch.
    """
    if not settings.api_token:
        return ""

    if authorization is None or authorization.credentials != settings.api_token:
        logger.warning("Unauthorized request — invalid or missing token")
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Invalid or missing token")

    return authorization.credentials
