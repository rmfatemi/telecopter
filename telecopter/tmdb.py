import asyncio
import aiohttp
from typing import List, Dict, Any, Optional

from telecopter.config import (
    TMDB_API_KEY,
    TMDB_BASE_URL,
    TMDB_IMAGE_BASE_URL,
    TMDB_REQUEST_DISAMBIGUATION_LIMIT,
)
from telecopter.logger import setup_logger

logger = setup_logger("tmdb")

TMDB_MEDIA_TYPE_MOVIE = "movie"
TMDB_MEDIA_TYPE_TV = "tv"

async def _make_tmdb_request(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    if not TMDB_API_KEY:
        logger.warning("tmdb api key is not configured. cannot make request to endpoint: %s", endpoint)
        return None

    base_params = {"api_key": TMDB_API_KEY}
    if params:
        base_params.update(params)

    url = f"{TMDB_BASE_URL}{endpoint}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=base_params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        "tmdb api request failed for endpoint %s with status %s: %s",
                        endpoint,
                        response.status,
                        await response.text(),
                    )
                    return None
    except aiohttp.ClientError as e:
        logger.error("aiohttp client error during tmdb api request to %s: %s", endpoint, e)
        return None
    except asyncio.TimeoutError:
        logger.error("timeout during tmdb api request to %s", endpoint)
        return None


def _extract_year(date_string: Optional[str]) -> Optional[int]:
    if date_string and isinstance(date_string, str) and len(date_string) >= 4:
        try:
            return int(date_string[:4])
        except ValueError:
            return None
    return None


def _format_search_result(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    media_type = result.get("media_type")
    tmdb_id = result.get("id")
    if not tmdb_id:
        return None

    title: Optional[str] = None
    year: Optional[int] = None
    poster_path: Optional[str] = result.get("poster_path")
    overview: Optional[str] = result.get("overview")

    if media_type == TMDB_MEDIA_TYPE_MOVIE:
        title = result.get("title") or result.get("original_title")
        year = _extract_year(result.get("release_date"))
    elif media_type == TMDB_MEDIA_TYPE_TV:
        title = result.get("name") or result.get("original_name")
        year = _extract_year(result.get("first_air_date"))
    else:
        return None

    if not title:
        return None

    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "year": year,
        "media_type": media_type,
        "overview": overview if overview else "no synopsis available.",
        "poster_url": f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None,
    }


async def search_media(query: str) -> List[Dict[str, Any]]:
    if not TMDB_API_KEY:
        logger.warning("tmdb search cannot be performed without an api key.")
        return []

    endpoint = "/search/multi"
    params = {"query": query, "page": 1, "include_adult": "false"}
    data = await _make_tmdb_request(endpoint, params)

    if data and "results" in data:
        formatted_results = []
        for item in data["results"]:
            formatted_item = _format_search_result(item)
            if formatted_item:
                formatted_results.append(formatted_item)
            if len(formatted_results) >= TMDB_REQUEST_DISAMBIGUATION_LIMIT:
                break
        logger.debug("tmdb search for '%s' found %s results.", query, len(formatted_results))
        return formatted_results
    logger.debug("tmdb search for '%s' found no results or failed.", query)
    return []


async def get_media_details(tmdb_id: int, media_type: str) -> Optional[Dict[str, Any]]:
    if not TMDB_API_KEY:
        logger.warning("tmdb details cannot be fetched without an api key.")
        return None

    if media_type not in [TMDB_MEDIA_TYPE_MOVIE, TMDB_MEDIA_TYPE_TV]:
        logger.error("invalid media_type '%s' for get_media_details.", media_type)
        return None

    endpoint = f"/{media_type}/{tmdb_id}"
    params_with_extras = {"append_to_response": "external_ids"}
    data = await _make_tmdb_request(endpoint, params_with_extras)

    if not data:
        logger.warning("failed to fetch details for %s id %s.", media_type, tmdb_id)
        return None

    title: Optional[str] = None
    year: Optional[int] = None
    overview: Optional[str] = data.get("overview")
    poster_path: Optional[str] = data.get("poster_path")
    imdb_id: Optional[str] = None

    external_ids_data = data.get("external_ids")
    if external_ids_data:
        imdb_id = external_ids_data.get("imdb_id")

    if not imdb_id and media_type == TMDB_MEDIA_TYPE_MOVIE:
        imdb_id = data.get("imdb_id")

    if media_type == TMDB_MEDIA_TYPE_MOVIE:
        title = data.get("title") or data.get("original_title")
        year = _extract_year(data.get("release_date"))
    elif media_type == TMDB_MEDIA_TYPE_TV:
        title = data.get("name") or data.get("original_name")
        year = _extract_year(data.get("first_air_date"))

    if not title:
        logger.warning("no title found for %s id %s after fetching details.", media_type, tmdb_id)
        return None

    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "year": year,
        "media_type": media_type,
        "overview": overview if overview else "no synopsis available.",
        "poster_url": f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None,
        "imdb_id": imdb_id,
        "genres": [genre["name"] for genre in data.get("genres", [])],
        "status": data.get("status"),
        "tagline": data.get("tagline"),
    }
