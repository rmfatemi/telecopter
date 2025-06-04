from typing import Optional, List, Union

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.formatting import Text, Bold, Italic, Code, as_list
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup, InlineKeyboardButton

import telecopter.database as db
from telecopter.utils import truncate_text
from telecopter.logger import setup_logger
from telecopter.config import DEFAULT_PAGE_SIZE
from telecopter.constants import (
    BTN_PREVIOUS_PAGE,
    BTN_NEXT_PAGE,
    BTN_BACK_TO_MAIN_MENU,
    MSG_NO_REQUESTS_YET,
    MSG_NO_MORE_REQUESTS,
    MSG_REQUESTS_PAGE_HEADER,
)

logger = setup_logger(__name__)

request_history_router = Router(name="request_history_router")


def get_my_requests_pagination_keyboard(page: int, total_pages: int) -> Optional[InlineKeyboardMarkup]:
    builder = InlineKeyboardBuilder()
    if page > 1:
        builder.button(text=BTN_PREVIOUS_PAGE, callback_data=f"my_req_page:{page - 1}")
    if page < total_pages:
        builder.button(text=BTN_NEXT_PAGE, callback_data=f"my_req_page:{page + 1}")
    if builder.buttons:
        builder.adjust(2)
        return builder.as_markup()
    return None


async def my_requests_entrypoint(
    base_message: Message, requesting_user_id: int, bot: Bot, state: FSMContext, is_callback: bool = False
):
    if not base_message or not base_message.chat:
        logger.warning("my_requests_entrypoint called with invalid base_message or chat.")
        return

    await _send_my_requests_page_logic(
        user_id=requesting_user_id,
        page=1,
        chat_id=base_message.chat.id,
        bot=bot,
        original_message_id=base_message.message_id,
        is_callback=is_callback,
        state=state,
    )


@request_history_router.callback_query(F.data.startswith("my_req_page:"))
async def my_requests_page_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message:
        return
    page = 1
    try:
        page = int(callback_query.data.split(":")[1])
    except (IndexError, ValueError):
        logger.warning(f"invalid page number in my_requests_page_cb: {callback_query.data}")

    await _send_my_requests_page_logic(
        user_id=callback_query.from_user.id,
        page=page,
        chat_id=callback_query.message.chat.id,
        bot=bot,
        original_message_id=callback_query.message.message_id,
        is_callback=True,
        state=state,
    )


async def _send_my_requests_page_logic(
    user_id: int, page: int, chat_id: int, bot: Bot, original_message_id: int, is_callback: bool, state: FSMContext
):
    await state.clear()

    logger.debug(f"Fetching requests for user_id: {user_id}, page: {page}")
    requests_rows = await db.get_user_requests(user_id, page, DEFAULT_PAGE_SIZE)
    total_requests = await db.get_user_requests_count(user_id)
    logger.debug(
        f"Found {len(requests_rows)} rows for this page, total_requests: {total_requests} for user_id: {user_id}"
    )

    total_pages = (total_requests + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
    total_pages = max(1, total_pages)

    page_content_elements: List[Union[Text, Bold, Italic, Code]] = []
    final_keyboard_builder = InlineKeyboardBuilder()

    if not requests_rows and page == 1:
        page_content_elements.append(Text(MSG_NO_REQUESTS_YET))
    elif not requests_rows and page > 1:
        page_content_elements.append(Text(MSG_NO_MORE_REQUESTS.format(page=page)))
        if page > 1:
            final_keyboard_builder.button(text=BTN_PREVIOUS_PAGE, callback_data=f"my_req_page:{page - 1}")
    else:
        page_content_elements.append(Bold(MSG_REQUESTS_PAGE_HEADER.format(page=page, total_pages=total_pages)))
        page_content_elements.append(Text("\n"))

        for req_row in requests_rows:
            req = dict(req_row)
            title_disp = truncate_text(req["title"], 50)
            req_type_icon = "🎬" if req["request_type"] in ["movie", "tv", "manual_media"] else "⚠️"
            date_req = req["created_at"][:10]

            request_item_parts: list[Union[Text, Bold, Italic, Code]] = [
                Text(f"\n{req_type_icon} "),
                Bold(title_disp),
                Text("\n  status: "),
                Italic(req["status"]),
                Text(", requested: "),
                Text(date_req),
            ]
            if req.get("user_note"):
                request_item_parts.extend([Text("\n  your note: "), Italic(truncate_text(req["user_note"], 70))])
            if req.get("admin_note"):
                request_item_parts.extend([Text("\n  admin note: "), Italic(truncate_text(req["admin_note"], 70))])
            request_item_parts.append(Text("\n---"))
            page_content_elements.append(as_list(*request_item_parts, sep=""))

        pagination_kb = get_my_requests_pagination_keyboard(page, total_pages)
        if pagination_kb:
            for row_buttons in pagination_kb.inline_keyboard:
                final_keyboard_builder.row(*row_buttons)

    final_keyboard_builder.row(
        InlineKeyboardButton(text=BTN_BACK_TO_MAIN_MENU, callback_data="main_menu:show_start_menu_from_my_requests")
    )

    keyboard_to_show = final_keyboard_builder.as_markup()

    if not page_content_elements and page == 1:
        final_text_object = Text(MSG_NO_REQUESTS_YET)
    elif page_content_elements:
        final_text_object = as_list(*page_content_elements, sep="\n")
    else:
        final_text_object = Text(MSG_NO_MORE_REQUESTS.format(page=page)) if page > 1 else Text(MSG_NO_REQUESTS_YET)

    text_to_send = final_text_object.as_markdown()

    try:
        if is_callback:
            await bot.edit_message_text(
                text=text_to_send,
                chat_id=chat_id,
                message_id=original_message_id,
                reply_markup=keyboard_to_show,
                parse_mode="MarkdownV2",
            )
        else:
            await bot.send_message(
                chat_id=chat_id, text=text_to_send, reply_markup=keyboard_to_show, parse_mode="MarkdownV2"
            )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug("message not modified for my_requests page %s, user %s.", page, user_id)
        else:
            logger.error("telegram badrequest in _send_my_requests_page_logic: %s for user %s", e, user_id)
    except Exception as e:
        logger.error("exception in _send_my_requests_page_logic: %s for user %s", e, user_id)
