"""Vercel serverless entry point — re-exports the FastAPI app."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from emergency_flights.web import app
