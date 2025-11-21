"""Expose FastAPI app instance for ASGI servers."""

from .main import app  # so `uvicorn src:app` or `uvicorn src.main:app` works

__all__ = ["app"] # from src import * pulls the fastapi instancce and skip everythign else. 
