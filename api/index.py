import os
import sys

# Ensure project root is available on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import demo

# Export the ASGI FastAPI application for Vercel
app = demo.app
