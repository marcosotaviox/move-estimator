import logging

import anthropic
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.routers import analysis, catalog, quotes
from app.services.image_service import InvalidImageError
from app.services.quote_service import (
    CompanyNotFoundError,
    InvalidQuoteError,
    ItemNotFoundError,
    QuoteLockedError,
    QuoteNotFoundError,
    SubmissionError,
)
from app.services.vision_service import VisionError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(analysis.router)
app.include_router(quotes.router)


# --- Error handling: domain errors -> HTTP responses, in one place ---

ERROR_STATUS: dict[type[Exception], int] = {
    CompanyNotFoundError: 404,
    QuoteNotFoundError: 404,
    ItemNotFoundError: 404,
    QuoteLockedError: 409,
    InvalidQuoteError: 422,
    InvalidImageError: 400,
}


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=ERROR_STATUS[type(exc)], content={"detail": str(exc)})


for error_class in ERROR_STATUS:
    app.add_exception_handler(error_class, domain_error_handler)


@app.exception_handler(SubmissionError)
async def submission_error_handler(request: Request, exc: SubmissionError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc), "problems": exc.problems})


async def ai_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("AI analysis failed: %s", exc)
    detail = "AI analysis failed, please try again"
    if settings.environment == "development":
        detail = f"{detail} | {type(exc).__name__}: {exc}"
    return JSONResponse(status_code=502, content={"detail": detail})


app.add_exception_handler(anthropic.APIError, ai_error_handler)
app.add_exception_handler(VisionError, ai_error_handler)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}