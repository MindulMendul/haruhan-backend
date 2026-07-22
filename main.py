"""Uvicorn entrypoint (uvicorn main:app) -- see app/main.py for the actual app."""

from app.main import app

__all__ = ["app"]
