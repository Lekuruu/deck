
from __future__ import annotations

from sqlalchemy.orm import Session
from fastapi import (
    HTTPException,
    APIRouter,
    Request,
    Depends,
    Query
)

from app.common.cache import status
from app.common.database import DBBeatmapset, DBUser
from app.common.constants import DisplayMode
from app.common.database.repositories import (
    beatmapsets,
    beatmaps,
    users,
    posts
)

import bcrypt
import utils
import app

router = APIRouter()

def online_beatmap(set: DBBeatmapset, post_id: int) -> str:
    versions = ",".join(
        [f"{beatmap.version}@{beatmap.mode}" for beatmap in set.beatmaps]
    )

    ratings = [
        r.rating for r in set.ratings
    ]

    average_rating = (
        sum(ratings) / len(ratings)
        if ratings else 0
    )

    status = {
        -2: "3",
        -1: "3",
        0: "3",
        1: "1",
        2: "2",
        3: "1",
        4: "2"
    }[set.status]

    return "|".join([
        f'{set.id} {set.artist} - {set.title}.osz',
        set.artist  if set.artist else "",
        set.title   if set.title else "",
        set.creator if set.creator else "",
        status,
        str(average_rating),
        str(set.last_update),
        str(set.id),
        str(set.topic_id or 0),
        str(int(set.has_video)),
        str(int(set.has_storyboard)),
        str(set.osz_filesize),
        str(set.osz_filesize_novideo),
        versions,
        str(post_id or 0),
    ])

@router.get('/osu-search.php')
def search(
    request: Request,
    session: Session = Depends(app.session.database.yield_session),
    legacy_password: str | None = Query(None, alias='c'),
    page_offset: int | None = Query(None, alias='p'),
    username: str | None = Query(None, alias='u'),
    password: str | None = Query(None, alias='h'),
    display_mode: int = Query(4, alias='r'),
    query: str = Query(..., alias='q'),
    mode: int = Query(-1, alias='m')
):
    supports_page_offset = page_offset is not None
    page_offset = page_offset or 0
    player = None

    # Skip authentication for old clients
    if legacy_password or password:
        if not (player := users.fetch_by_name(username, session=session)):
            return '-1\nFailed to authenticate user'

        if not bcrypt.checkpw((password or legacy_password).encode(), player.bcrypt.encode()):
            return '-1\nFailed to authenticate user'

        if not status.exists(player.id):
            return '-1\nNot connected to bancho'

        if not player.is_supporter:
            return "-1\nWhy are you here?"

    if display_mode not in DisplayMode._value2member_map_:
        return "-1\nInvalid display mode"

    display_mode = DisplayMode(display_mode)

    if len(query) < 2:
        return "-1\nQuery is too short."

    app.session.logger.info(
        f'Got osu!direct search request: "{query}" '
        f'from "{player}"'
    )

    response = []

    try:
        results = beatmapsets.search(
            query,
            player.id if player else 0,
            display_mode,
            page_offset * 100,
            mode,
            session
        )

        if not supports_page_offset:
            response.append(str(
                len(results)
            ))

        else:
            response.append(str(
                len(results)
                if len(results) < 100 else 101
            ))

        for set in results:
            post_id = posts.fetch_initial_post_id(set.topic_id, session)
            response.append(online_beatmap(set, post_id))
    except Exception as e:
        app.session.logger.error(f'Failed to execute search: {e}', exc_info=e)
        return "-1\nServer error. Please try again!"

    utils.track(
        'direct_search',
        user=player,
        request=request,
        properties={
            'query': query,
            'mode': mode,
            'results': len(results),
            'display_mode': display_mode.name,
            'page': page_offset
        }
    )

    return "\n".join(response)

@router.get('/osu-search-set.php')
def pickup_info(
    request: Request,
    session: Session = Depends(app.session.database.yield_session),
    beatmap_id: int | None = Query(None, alias='b'),
    topic_id: int | None = Query(None, alias='t'),
    checksum: int | None = Query(None, alias='c'),
    post_id: int | None = Query(None, alias='p'),
    set_id: int | None = Query(None, alias='s'),
    username: str | None = Query(None, alias='u'),
    password: str | None = Query(None, alias='h'),
):
    beatmapset: DBBeatmapset | None = None
    player: DBUser | None = None

    # Skip authentication for old clients
    if username and password:
        if not (player := users.fetch_by_name(username, session=session)):
            raise HTTPException(401)

        if not bcrypt.checkpw(password.encode(), player.bcrypt.encode()):
            raise HTTPException(401)

        if not player.is_supporter:
            raise HTTPException(401)

    if topic_id:
        # TODO
        raise HTTPException(404)

    if post_id:
        # TODO
        raise HTTPException(404)

    if beatmap_id:
        beatmap = beatmaps.fetch_by_id(beatmap_id, session)
        beatmapset = beatmap.beatmapset if beatmap else None

    if checksum:
        beatmap = beatmaps.fetch_by_checksum(checksum, session)
        beatmapset = beatmap.beatmapset if beatmap else None

    if set_id:
        beatmapset = beatmapsets.fetch_one(set_id, session)

    if not beatmapset:
        app.session.logger.warning("osu!direct pickup request failed: Not found")
        raise HTTPException(404)

    app.session.logger.info(
        f'Got osu!direct pickup request for: "{beatmapset.full_name}" '
        f'from "{player}"'
    )

    if not beatmapset.osz_filesize:
        utils.update_osz_filesize(
            beatmapset.id,
            beatmapset.has_video
        )

    utils.track(
        'direct_pickup',
        user=player,
        request=request,
        properties={
            'name': beatmapset.full_name,
            'id': beatmapset.id
        }
    )

    return online_beatmap(
        beatmapset,
        posts.fetch_initial_post_id(beatmapset.topic_id, session)
    )
