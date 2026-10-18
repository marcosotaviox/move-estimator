import logging

import anthropic
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.schemas.analysis import PhotoAnalysis
from app.services.analysis_service import analyse_photo
from app.services.image_service import InvalidImageError
from app.services.vision_service import VisionError

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

router = APIRouter(prefix="/analyze", tags=["analysis"])


@router.post("/photo", response_model=PhotoAnalysis)
def analyze_photo(file: UploadFile = File(...), room: str = Form("living room")):
    data = file.file.read()

    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 15 MB)")

    try:
        return analyse_photo(data, room)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (anthropic.APIError, VisionError) as exc:
        logger.exception("AI analysis failed")
        detail = "AI analysis failed, please try again"
        if get_settings().environment == "development":
            detail = f"{detail} | {type(exc).__name__}: {exc}"
        raise HTTPException(status_code=502, detail=detail)