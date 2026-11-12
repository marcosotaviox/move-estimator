from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.quotes import (
    PhotoUploadResult,
    QuoteCreate,
    QuoteItemCreate,
    QuoteItemUpdate,
    QuoteOut,
    QuoteUpdate,
)
from app.services import quote_service

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

router = APIRouter(tags=["quotes"])


@router.post("/companies/{slug}/quotes", response_model=QuoteOut, status_code=201)
def create_quote(slug: str, data: QuoteCreate):
    return quote_service.create_quote(slug, data)


@router.get("/quotes/{quote_id}", response_model=QuoteOut)
def read_quote(quote_id: UUID):
    return quote_service.get_quote(quote_id)


@router.patch("/quotes/{quote_id}", response_model=QuoteOut)
def update_quote(quote_id: UUID, data: QuoteUpdate):
    return quote_service.update_quote(quote_id, data)


@router.post("/quotes/{quote_id}/photos", response_model=PhotoUploadResult)
def upload_photo(quote_id: UUID, file: UploadFile = File(...), room: str = Form(...)):
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 15 MB)")
    return quote_service.add_photo(quote_id, data, room)


@router.post("/quotes/{quote_id}/items", response_model=QuoteOut, status_code=201)
def add_item(quote_id: UUID, data: QuoteItemCreate):
    return quote_service.add_item(quote_id, data)


@router.patch("/quotes/{quote_id}/items/{item_id}", response_model=QuoteOut)
def update_item(quote_id: UUID, item_id: UUID, data: QuoteItemUpdate):
    return quote_service.update_item(quote_id, item_id, data)


@router.delete("/quotes/{quote_id}/items/{item_id}", response_model=QuoteOut)
def delete_item(quote_id: UUID, item_id: UUID):
    return quote_service.delete_item(quote_id, item_id)


@router.post("/quotes/{quote_id}/submit", response_model=QuoteOut)
def submit_quote(quote_id: UUID):
    return quote_service.submit_quote(quote_id)