"""
Vercel FastAPI service entrypoint.
Re-exports `app` from backend/server.py for uvicorn auto-detection.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from server import app  # noqa: F401, E402
