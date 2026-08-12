import logging
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import routes_health, routes_video, routes_groq
from app.utils.file_manager import STORAGE_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vidai")

app = FastAPI(title="VidAI Studio API", version="1.0.0")

frontend_urls = [u.strip() for u in os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_urls or ["*"],
    # Also allow any localhost/127.0.0.1 port in dev (Vite sometimes picks a
    # different port if 5173 is busy, or you open via 127.0.0.1 instead of
    # localhost). Without this, requests fail silently in the browser and
    # the UI just looks like "nothing happens" when you click Generate.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

app.include_router(routes_health.router)
app.include_router(routes_video.router)
app.include_router(routes_groq.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."},
    )


@app.get("/")
async def root():
    return {"name": "VidAI Studio API", "status": "running", "docs": "/docs"}
