from typing import Optional, List, Union

from aiogram.utils.formatting import Text, Bold, Italic, TextLink, Code, as_list

from telecopter.logger import setup_logger
from telecopter.config import TMDB_MOVIE_URL_BASE, TMDB_TV_URL_BASE, IMDB_TITLE_URL_BASE


logger = setup_logger(__name__)


def make_tmdb_url(tmdb_id: int, media_type: str) -> Optional[str]:
    if media_type == "movie":
        return f"{TMDB_MOVIE_URL_BASE}{tmdb_id}"
    elif media_type == "tv":
        return f"{TMDB_TV_URL_BASE}{tmdb_id}"
    logger.warning("unsupported media type '%s' for tmdb url generation.", media_type)
    return None


def make_imdb_url(imdb_id: str) -> Optional[str]:
    if imdb_id and imdb_id.startswith("tt"):
        return f"{IMDB_TITLE_URL_BASE}{imdb_id}/"
    logger.debug("invalid or missing imdb_id '%s' for imdb url generation.", imdb_id)
    return None


def truncate_text(text: str, max_length: int, ellipsis: str = "...") -> str:
    if not isinstance(text, str):
        return ""
    if len(text) > max_length:
        return text[: max_length - len(ellipsis)] + ellipsis
    return text


def format_media_details_for_user(details: dict, for_admin_notification: bool = False) -> Text:
    if not details:
        return Text("error: could not retrieve media details.")

    title_str = details.get("title", "n/a")
    year = details.get("year")
    year_str = f" ({year})" if year else ""

    media_type_display = "movie" if details.get("media_type") == "movie" else "tv show"
    overview_max_len = 300 if for_admin_notification else 500
    overview_text = Text(truncate_text(details.get("overview", "no synopsis available."), overview_max_len))

    content_elements: list[Union[str, Text, Bold, Italic, TextLink]] = [
        Bold(f"{title_str}{year_str}"),
        Text(f" ({media_type_display})\n"),
        overview_text,
    ]

    links: List[Union[Text, TextLink]] = []
    tmdb_url = make_tmdb_url(details["tmdb_id"], details["media_type"])
    if tmdb_url:
        links.append(TextLink("view on tmdb", url=tmdb_url))

    imdb_id_val = details.get("imdb_id")
    if imdb_id_val:
        imdb_url = make_imdb_url(imdb_id_val)
        if imdb_url:
            if links:
                links.append(Text(" | "))
            links.append(TextLink("view on imdb", url=imdb_url))

    if links:
        content_elements.append(Text("\n"))
        content_elements.extend(links)

    return Text(*content_elements)


def format_request_for_admin(request_data: dict, user_info: Optional[dict] = None) -> Text:
    req_id = request_data["request_id"]
    req_type = request_data["request_type"]
    req_title_raw = request_data["title"]
    req_status_raw = request_data["status"]
    user_query_raw = request_data.get("user_query", "n/a")
    user_note_raw = request_data.get("user_note", "n/a")

    user_display_elements: List[Union[Text, Code, TextLink]]
    if user_info:
        user_fn = user_info.get("first_name", "user")
        user_username = user_info.get("username")
        user_id = user_info["user_id"]

        if user_username:
            user_display_elements = [TextLink(text=f"@{user_username}", url=f"tg://user?id={user_id}")]
        elif user_fn:
            user_display_elements = [Text(user_fn), Text(" (id: "), Code(str(user_id)), Text(")")]
        else:
            user_display_elements = [Text("user (id: "), Code(str(user_id)), Text(")")]
    else:
        user_display_elements = [Text("unknown user")]

    message_items: List[Union[str, Text, Bold, Italic, Code, TextLink]] = [
        Bold("new request notification"),
        Text(Bold("request id:"), " ", Code(str(req_id))),
        Text(Bold("user:"), " ", *user_display_elements),
        Text(Bold("type:"), " ", Text(req_type)),
        Text(Bold("title/summary:"), " ", Text(req_title_raw)),
    ]

    if req_type in ["movie", "tv"]:
        year = request_data.get("year")
        if year:
            message_items.append(Text(Bold("year:"), " ", Text(str(year))))

        tmdb_id = request_data.get("tmdb_id")
        if tmdb_id:
            tmdb_url = make_tmdb_url(tmdb_id, req_type)
            if tmdb_url:
                message_items.append(Text(Bold("tmdb:"), " ", TextLink("link", url=tmdb_url)))

        imdb_id_val = request_data.get("imdb_id")
        if imdb_id_val:
            imdb_url = make_imdb_url(imdb_id_val)
            if imdb_url:
                message_items.append(Text(Bold("imdb:"), " ", TextLink("link", url=imdb_url)))

        message_items.append(Text(Bold("user query:"), " ", Code(user_query_raw)))

    message_items.append(Text(Bold("user note:"), " ", Italic(user_note_raw)))
    message_items.append(Text(Bold("status:"), " ", Text(req_status_raw)))

    return as_list(*message_items, sep="\n\n")
