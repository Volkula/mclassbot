from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from api.routes import events, registrations, miniapp
from database.database import init_db

app = FastAPI(title="Event Registration API", version="1.0.0")

# CORS middleware для работы с Telegram WebApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы для мини-приложения
miniapp_path = Path(__file__).parent.parent / "miniapp"
if miniapp_path.exists():
    app.mount("/static", StaticFiles(directory=str(miniapp_path)), name="static")

# Инициализация БД
init_db()

# Регистрация роутеров
app.include_router(events.router)
app.include_router(registrations.router)
app.include_router(miniapp.router)


@app.get("/")
async def root():
    return {"message": "Event Registration API"}


@app.get("/health")
async def health():
    return {"status": "ok"}

