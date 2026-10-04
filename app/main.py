"""FastAPI entrypoint for Play Pulse."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .models import GameIdea
from .service import (
    SerpApiError,
    run_brief,
    run_trend_scan,
    sample_brief,
    sample_trend_scan,
)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Play Pulse", version="1.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _setup_error(request: Request, hint: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "heading": "Setup required — no SerpApi key",
            "message": (
                "Play Pulse will not invent live Play data. Copy .env.example to .env, "
                "set SERPAPI_API_KEY from https://serpapi.com/users/sign_up, then restart."
            ),
            "hint": hint,
        },
        status_code=503,
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "has_api_key": settings.has_api_key,
            "error": None,
        },
    )


@app.post("/trends", response_class=HTMLResponse)
async def trends_route(request: Request) -> HTMLResponse:
    settings = get_settings()
    if not settings.has_api_key:
        return _setup_error(
            request,
            "You can open the SAMPLE trend preview to see the layout without credits.",
        )
    try:
        scan = run_trend_scan(settings)
    except SerpApiError as exc:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "heading": "SerpApi error",
                "message": str(exc),
                "hint": "Check the key, remaining credits, and network, then try again.",
            },
            status_code=502,
        )
    return templates.TemplateResponse(
        request,
        "trends.html",
        scan.to_template_dict(),
    )


@app.get("/sample", response_class=HTMLResponse)
@app.get("/sample/trends", response_class=HTMLResponse)
async def sample_trends_route(request: Request) -> HTMLResponse:
    scan = sample_trend_scan()
    return templates.TemplateResponse(
        request,
        "trends.html",
        scan.to_template_dict(),
    )


@app.get("/sample/idea", response_class=HTMLResponse)
async def sample_idea_route(request: Request) -> HTMLResponse:
    brief = sample_brief()
    return templates.TemplateResponse(
        request,
        "brief.html",
        brief.to_template_dict(),
    )


@app.post("/analyze", response_class=HTMLResponse)
async def analyze_route(
    request: Request,
    title: str = Form(...),
    pitch: str = Form(...),
    keywords: str = Form(""),
) -> HTMLResponse:
    settings = get_settings()
    idea = GameIdea(title=title.strip(), pitch=pitch.strip(), keywords=keywords.strip())
    if not idea.title or not idea.pitch:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "has_api_key": settings.has_api_key,
                "error": "Title and one-line pitch are required for idea check.",
                "title": title,
                "pitch": pitch,
                "keywords": keywords,
            },
            status_code=400,
        )
    if not settings.has_api_key:
        return _setup_error(
            request,
            "You can open the SAMPLE idea preview to see the brief layout without credits.",
        )
    try:
        brief = run_brief(idea, settings)
    except SerpApiError as exc:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "heading": "SerpApi error",
                "message": str(exc),
                "hint": "Check the key, remaining credits, and network, then try again.",
            },
            status_code=502,
        )
    return templates.TemplateResponse(
        request,
        "brief.html",
        brief.to_template_dict(),
    )


@app.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "ok": True,
        "has_api_key": settings.has_api_key,
        "service": "play-pulse",
    }
