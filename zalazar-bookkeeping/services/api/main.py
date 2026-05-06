from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from .routes import plaid, queue, jarvis, reports, health, entities, meta, transactions, notifications, reconciliation, bank_accounts
from zalazar.scheduler import scheduler
from zalazar.config import settings

logger = structlog.get_logger()

# Initialize Sentry
if settings.SENTRY_DSN and settings.SENTRY_DSN.startswith("http"):
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=1.0,
        environment=settings.ENVIRONMENT,
    )
    logger.info("Sentry initialized")
else:
    logger.info("Sentry skipped (invalid or missing DSN)")

app = FastAPI(title="Zalazar Bookkeeping API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(plaid.router)
app.include_router(queue.router)
app.include_router(transactions.router)
app.include_router(jarvis.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(health.router)
app.include_router(entities.router)
app.include_router(meta.router)
app.include_router(reconciliation.router)
app.include_router(bank_accounts.router)
@app.get("/")
async def root():
    return {"message": "Zalazar Bookkeeping API is online", "status": "running"}


@app.on_event("startup")
async def startup_event():
    logger.info("API Starting Up")
    await scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API Shutting Down")
