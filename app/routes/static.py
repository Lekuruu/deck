
from fastapi.responses import StreamingResponse
from fastapi import (
    HTTPException,
    APIRouter,
    Response,
    Query
)

import bcrypt
import app

router = APIRouter()

@router.get('/mt/{id}')
def direct_cover(id: str):
    if not (image := app.session.storage.get_background(id)):
        return

    return image

@router.get('/mp3/preview/{filename}')
def mp3(filename: str):
    set_id = int(filename.replace('.mp3', ''))

    if not (mp3 := app.session.storage.get_mp3(set_id)):
        return

    return mp3

@router.get('/d/{id}')
def osz(
    id: str,
    username: str = Query(..., alias='u'),
    password: str = Query(..., alias='h')
):
    if not (user := app.session.database.user_by_name(username)):
        raise HTTPException(401)

    if not bcrypt.checkpw(password.encode(), user.bcrypt.encode()):
        raise HTTPException(401)

    set_id = int(id.replace('n', ''))
    no_video = 'n' in id

    if not (osz := app.session.storage.api.osz(set_id)):
        return

    return StreamingResponse(osz)

# TODO: Move to seperate server
