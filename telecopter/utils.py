from typing import Optional, List, Union, Dict, Any

from aiogram.utils.formatting import Text, Bold, Italic, TextLink, Code, as_list

from telecopter.logger import setup_logger
from telecopter.config import TMDB_MOVIE_URL_BASE, TMDB_TV_URL_BASE, IMDB_TITLE_URL_BASE
from telecopter.constants import (
    MediaType,
    Icon,
    RequestType,
)


logger = setup_logger(__name__)


def make_tmdb_url(tmdb_id: int, media_type: str) -> Optional[str]:
    if media_type == MediaType.MOVIE.value:
        return f"{TMDB_MOVIE_URL_BASE}{tmdb_id}"
    elif media_type == MediaType.TV.value:
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


def format_media_details_for_user(details: Dict, for_admin_notification: bool = False) -> Text:
    if not details:
        return Text("Error: Could not retrieve media details.")

    title_str = details.get("title", "N/A")
    year = details.get("year")
    year_str = f" ({year})" if year else ""

    media_type = details.get("media_type")
    media_type_icon_and_name_str = ""
    if media_type == MediaType.MOVIE.value:
        media_type_icon_and_name_str = f"{Icon.MOVIE.value} Movie"
    elif media_type == MediaType.TV.value:
        media_type_icon_and_name_str = f"{Icon.TV_SHOW.value} TV Show"

    overview_max_len = 300 if for_admin_notification else 500
    overview_content = details.get("overview", "No synopsis available.")
    overview_text = Text(truncate_text(overview_content, overview_max_len))

    content_elements: list[Union[Text, Bold, Italic, TextLink]] = [
        Bold(f"{title_str}{year_str}"),
        Text(f" ({media_type_icon_and_name_str})\n" if media_type_icon_and_name_str else "\n"),
        overview_text,
    ]

    links: List[Union[Text, TextLink]] = []

    if "tmdb_id" in details and "media_type" in details:
        tmdb_url = make_tmdb_url(details["tmdb_id"], details["media_type"])
        if tmdb_url:
            links.append(TextLink("View on TMDB", url=tmdb_url))

    imdb_id_val = details.get("imdb_id")
    if imdb_id_val:
        imdb_url = make_imdb_url(imdb_id_val)
        if imdb_url:
            if links:
                links.append(Text(" | "))
            links.append(TextLink("View on IMDB", url=imdb_url))

    if links:
        content_elements.append(Text("\n"))
        content_elements.extend(links)

    return Text(*content_elements)


def format_request_for_admin(request_data: Dict, user_info: Optional[Dict] = None) -> Text:
    req_id = request_data["request_id"]
    req_type = request_data["request_type"]
    req_title_raw = request_data["title"]
    req_status_raw = request_data["status"]
    user_query_raw = request_data.get("user_query", "N/A")
    user_note_raw = request_data.get("user_note", "N/A")

    user_display_elements: List[Union[Text, Code, TextLink]]
    if user_info:
        user_fn = user_info.get("first_name")
        user_username = user_info.get("username")
        user_id = user_info["user_id"]

        if user_username:
            user_display_elements = [TextLink(text=f"@{user_username}", url=f"tg://user?id={user_id}")]
        elif user_fn:
            user_display_elements = [Text(user_fn), Text(" (ID: "), Code(str(user_id)), Text(")")]
        else:
            user_display_elements = [Text("User (ID: "), Code(str(user_id)), Text(")")]
    else:
        user_display_elements = [Italic("Unknown user")]

    req_type_icon_str: str
    req_type_display_name: str

    if req_type == MediaType.MOVIE.value:
        req_type_icon_str = Icon.MOVIE.value
        req_type_display_name = "Movie"
    elif req_type == MediaType.TV.value:
        req_type_icon_str = Icon.TV_SHOW.value
        req_type_display_name = "TV Show"
    elif req_type == MediaType.MANUAL.value:
        req_type_icon_str = Icon.MANUAL_REQUEST.value
        req_type_display_name = "Manual Request"
    elif req_type == RequestType.PROBLEM.value:
        req_type_icon_str = Icon.PROBLEM_REPORT.value
        req_type_display_name = "Problem Report"
    else:
        req_type_icon_str = Icon.GENERIC_REQUEST.value
        req_type_display_name = req_type.replace("_", " ").title() if req_type else "Unknown Type"

    message_items: List[Union[Text, Bold, Italic, Code, TextLink]] = [
        Bold("New Request Notification"),
        Text(Bold("Request ID:"), " ", Code(str(req_id))),
        Text(Bold("User:"), " ", *user_display_elements),
        Text(Bold("Type:"), " ", req_type_icon_str, " ", req_type_display_name),
        Text(Bold("Title:"), " ", Italic(req_title_raw)),
    ]

    if req_type in [MediaType.MOVIE.value, MediaType.TV.value, MediaType.MANUAL.value]:
        year_val = request_data.get("year")
        if year_val:
            message_items.append(Text(Bold("Year:"), " ", Text(str(year_val))))

        tmdb_id_val = request_data.get("tmdb_id")
        if tmdb_id_val is not None and req_type in [MediaType.MOVIE.value, MediaType.TV.value]:
            tmdb_url = make_tmdb_url(tmdb_id_val, req_type)
            if tmdb_url:
                message_items.append(Text(Bold("TMDB:"), " ", TextLink("Link", url=tmdb_url)))

        imdb_id_val = request_data.get("imdb_id")
        if imdb_id_val:
            imdb_url = make_imdb_url(imdb_id_val)
            if imdb_url:
                if message_items:
                    message_items.append(Text(" | "))  # Adjusting for correct placement
                message_items.append(TextLink("View on IMDB", url=imdb_url))

        if user_query_raw and user_query_raw != "N/A":
            message_items.append(Text(Bold("User Query:"), " ", Code(user_query_raw)))

    if user_note_raw and user_note_raw != "N/A":
        message_items.append(Text(Bold("User Note:"), " ", Italic(user_note_raw)))

    message_items.append(Text(Bold("Status:"), " ", Italic(req_status_raw)))

    return as_list(*message_items, sep="\n")


def format_request_item_display_parts(
    request_data: Dict[str, Any], view_context: str, submitter_name_override: Optional[str] = None
) -> List[Union[Text, Bold, Italic, Code]]:
    req_id = request_data.get("request_id")
    req_type = request_data["request_type"]
    req_title = request_data.get("title", "N/A")
    req_status = request_data.get("status", "N/A")
    created_at_raw = request_data.get("created_at")
    created_date = str(created_at_raw)[:10] if isinstance(created_at_raw, str) else "Unknown Date"
    task_user_id = request_data.get("user_id")

    item_icon_str: str
    request_type_display_str: str

    if req_type == MediaType.MOVIE.value:
        item_icon_str = Icon.MOVIE.value
        request_type_display_str = "Movie"
    elif req_type == MediaType.TV.value:
        item_icon_str = Icon.TV_SHOW.value
        request_type_display_str = "TV Show"
    elif req_type == MediaType.MANUAL.value:
        item_icon_str = Icon.MANUAL_REQUEST.value
        request_type_display_str = "Manual Request"
    elif req_type == RequestType.PROBLEM.value:
        item_icon_str = Icon.PROBLEM_REPORT.value
        request_type_display_str = "Problem Report"
    else:
        item_icon_str = Icon.GENERIC_REQUEST.value
        request_type_display_str = req_type.replace("_", " ").title() if req_type else "Task"

    display_parts: List[Union[Text, Bold, Italic, Code]] = [Text(item_icon_str, " ", Bold(request_type_display_str))]
    title_trunc_length = 40 if view_context == "admin_list_item" else 50
    display_parts.append(Text("\n", Bold("Title: "), Italic(truncate_text(req_title, title_trunc_length))))
    if view_context == "admin_list_item" and req_id:
        display_parts.append(Text("\n", Bold("ID: "), Code(str(req_id))))

    display_parts.append(Text("\n", Bold("Status: "), Italic(req_status)))

    date_label = "Requested" if view_context == "user_history_item" else "On"
    display_parts.append(Text("\n", Bold(f"{date_label}: "), created_date))

    if view_context == "admin_list_item":
        if submitter_name_override:
            display_parts.append(Text("\n", Bold("By: "), submitter_name_override))
        elif task_user_id:
            display_parts.append(Text("\n", Bold("By User ID: "), Code(str(task_user_id))))

    user_note = request_data.get("user_note")
    admin_note = request_data.get("admin_note")
    note_trunc_len = 70

    if user_note and view_context == "admin_list_item":
        display_parts.append(Text("\n", Bold("User Note: "), Italic(truncate_text(user_note, note_trunc_len))))
    elif user_note and view_context == "user_history_item":
        display_parts.append(Text("\n", Bold("Your Note: "), Italic(truncate_text(user_note, note_trunc_len))))

    if view_context == "user_history_item" and admin_note:
        display_parts.append(Text("\n", Bold("Admin Note: "), Italic(truncate_text(admin_note, note_trunc_len))))

    return display_parts
