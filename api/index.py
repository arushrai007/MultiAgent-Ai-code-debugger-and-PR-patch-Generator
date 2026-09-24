import os
import sys
from fastapi import FastAPI, Request
import gradio as gr

# Ensure project root is available on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import demo

app = FastAPI(title="DebugFlow AI")

@app.middleware("http")
async def normalize_vercel_paths(request: Request, call_next):
    raw_path = request.scope.get("path", "")
    if raw_path.startswith("/api/index.py"):
        normalized = raw_path[len("/api/index.py"):]
        request.scope["path"] = normalized if normalized else "/"
    elif raw_path.startswith("/api/index"):
        normalized = raw_path[len("/api/index"):]
        request.scope["path"] = normalized if normalized else "/"
    elif raw_path.startswith("/api"):
        normalized = raw_path[len("/api"):]
        request.scope["path"] = normalized if normalized else "/"
    
    return await call_next(request)

app = gr.mount_gradio_app(app, demo, path="/")
