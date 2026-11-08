import logging
from uuid import UUID

import anthropic
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.schemas.quotes import PhotoUploadResult, QuoteCreate, QuoteOut, QuoteUpdate
from app.services.image_service import InvalidImageError
from app.services.quote_service import (
    CompanyNotFoundError,
    InvalidQuoteError,
    QuoteNotFoundError,
    add_photo,
    create_quote,
    get_quote,
    update_quote,
)
from app.services.vision_service import VisionError

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

router = APIRouter(tags=["quotes"])


@router.post("/companies/{slug}/quotes", response_model=QuoteOut, status_code=201)
def create(slug: str, data: QuoteCreate):
    try:
        return create_quote(slug, data)
    except CompanyNotFoundError:
        raise HTTPException(status_code=404, detail="Company not found")


@router.get("/quotes/{quote_id}", response_model=QuoteOut)
def read(quote_id: UUID):
    try:
        return get_quote(quote_id)
    except QuoteNotFoundError:
        raise HTTPException(status_code=404, detail="Quote not found")


@router.patch("/quotes/{quote_id}", response_model=QuoteOut)
def update(quote_id: UUID, data: QuoteUpdate):
    try:
        return update_quote(quote_id, data)
    except QuoteNotFoundError:
        raise HTTPException(status_code=404, detail="Quote not found")
    except InvalidQuoteError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/quotes/{quote_id}/photos", response_model=PhotoUploadResult)
def upload_photo(quote_id: UUID, file: UploadFile = File(...), room: str = Form(...)):
    data = file.file.read()

    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 15 MB)")

    try:
        return add_photo(quote_id, data, room)
    except QuoteNotFoundError:
        raise HTTPException(status_code=404, detail="Quote not found")
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (anthropic.APIError, VisionError) as exc:
        logger.exception("AI analysis failed")
        detail = "AI analysis failed, please try again"
        if get_settings().environment == "development":
            detail = f"{detail} | {type(exc).__name__}: {exc}"
        raise HTTPException(status_code=502, detail=detail)