
from app.common.database.repositories import screenshots

from fastapi import (
    HTTPException,
    APIRouter,
    Response
)

import app

router = APIRouter()

@router.get('/')
def index():
    raise HTTPException(404)

@router.get('/{id}')
def get_screenshot(id: int):
    if not (ss := screenshots.fetch_by_id(id)):
        raise HTTPException(404)
    
    if ss.hidden:
        raise HTTPException(404)

    if not (image := app.session.storage.get_screenshot(id)):
        raise HTTPException(404)

    return Response(image)

# TODO: Move to seperate server
