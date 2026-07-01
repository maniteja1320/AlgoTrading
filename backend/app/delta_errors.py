import requests
from fastapi import HTTPException


def raise_delta_error(exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, ValueError):        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, requests.HTTPError):
        detail = str(exc)
        status = 401 if "401" in detail or "Unauthorized" in detail else 502
        raise HTTPException(status_code=status, detail=detail) from exc
    if isinstance(exc, Exception) and "Api_key or Api_secret missing" in str(exc):
        raise HTTPException(status_code=503, detail="Delta API credentials not configured") from exc
    raise HTTPException(status_code=502, detail=str(exc)) from exc
