from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from app.config import settings
from app.database import engine, Base
from app.routers import alerts, rules, users, analytics, audit, webhooks, auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Starting Alert Intelligence [{settings.APP_ENV}]")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    print("👋 Shutting down")
    await engine.dispose()

app = FastAPI(title="Alert Intelligence Dashboard", version="1.0.0", docs_url="/api/docs" if settings.APP_DEBUG else None, lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.time() - start)
    return response

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(rules.router, prefix="/api/rules", tags=["Rules"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "alert-intelligence"}

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
