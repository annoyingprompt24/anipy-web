from fastapi import APIRouter, Query, HTTPException
from anipy_api.anime import Anime
from anipy_api.provider import LanguageTypeEnum

router = APIRouter()


@router.get("/search")
def search_anime(q: str = Query(..., min_length=1)):
    try:
        results = Anime.search(q)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return [
        {
            "id": a.identifier,
            "name": a.name,
            "languages": [l.value for l in (a.languages or [])],
        }
        for a in results[:20]
    ]


@router.get("/episodes")
def get_episodes(anime_id: str = Query(...), lang: str = Query("sub")):
    lang_enum = LanguageTypeEnum.SUB if lang == "sub" else LanguageTypeEnum.DUB
    try:
        results = Anime.search(anime_id)
        if not results:
            raise HTTPException(status_code=404, detail="Anime not found")
        anime = results[0]
        episodes = anime.get_episodes(lang_enum)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return [{"number": e.number} for e in episodes]
