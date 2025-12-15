from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter(tags=["miniapp"])


@router.get("/", response_class=HTMLResponse)
async def miniapp_index():
    """Главная страница мини-приложения"""
    html_file = Path(__file__).parent.parent.parent / "miniapp" / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<html><body><h1>Mini App</h1></body></html>"

