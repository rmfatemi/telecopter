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


logger = setup_logger(__name__)

request_history_router = Router(name="request_history_router")


def get_my_requests_pagination_keyboard(page: int, total_pages: int) -> Optional[InlineKeyboardMarkup]:
    builder = InlineKeyboardBuilder()
    if page > 1:
        builder.button(text="⬅️ previous", callback_data=f"my_req_page:{page - 1}")
    if page < total_pages:
        builder.button(text="next ➡️", callback_data=f"my_req_page:{page + 1}")
    if builder.buttons:
        builder.adjust(2)
        return builder.as_markup()
    return None


async def my_requests_entrypoint(
        message: Message, bot: Bot, state: FSMContext, is_callback: bool = False
):
    if not message.from_user:
        return
    await _send_my_requests_page_logic(
        message.from_user.id, 1, message.chat.id, bot,
        original_message_id=message.message_id,
        is_callback=is_callback, state=state,
    )


@request_history_router.callback_query(F.data.startswith("my_req_page:"))
async def my_requests_page_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message: return
    page = 1
    try:
        page = int(callback_query.data.split(":")[1])
    except (IndexError, ValueError):
        logger.warning(f"invalid page number in my_requests_page_cb: {callback_query.data}")

    await _send_my_requests_page_logic(
        callback_query.from_user.id, page, callback_query.message.chat.id, bot,
        original_message_id=callback_query.message.message_id,
        is_callback=True, state=state,
    )


async def _send_my_requests_page_logic(
        user_id: int, page: int, chat_id: int, bot: Bot, original_message_id: int, is_callback: bool, state: FSMContext
):
    await state.clear()
    requests_rows = await db.get_user_requests(user_id, page, DEFAULT_PAGE_SIZE)
    total_requests = await db.get_user_requests_count(user_id)
    total_pages = (total_requests + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
    total_pages = max(1, total_pages)

    page_content_elements: List[Union[Text, Bold, Italic, Code]] = []
    final_keyboard_builder = InlineKeyboardBuilder()

    if not requests_rows and page == 1:
        page_content_elements.append(Text("🤷 you haven't made any requests or reports yet."))
        final_keyboard_builder.button(text="🎬 request media", callback_data="main_menu:request_media")
        final_keyboard_builder.button(text="⚠️ report a problem", callback_data="main_menu:report_problem")
        final_keyboard_builder.adjust(1)
    elif not requests_rows and page > 1:
        page_content_elements.append(Text(f"✅ no more requests found on page {page}."))
        if page > 1:
            final_keyboard_builder.button(text="⬅️ previous", callback_data=f"my_req_page:{page - 1}")
    else:
        page_content_elements.append(Bold(f"📖 your requests & reports (page {page} of {total_pages})"))
        page_content_elements.append(Text("\n"))

        for req_row in requests_rows:
            req = dict(req_row)
            title_disp = truncate_text(req["title"], 50)
            req_type_icon = "🎬" if req["request_type"] in ["movie", "tv", "manual_media"] else "⚠️"
            date_req = req["created_at"][:10]

            request_item_parts: list[Union[Text, Bold, Italic, Code]] = [
                Text(f"\n{req_type_icon} "), Bold(title_disp),
                Text(f"\n  status: "), Italic(req["status"]),
                Text(f", requested: "), Text(date_req),
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
        InlineKeyboardButton(text="⬅️ back to main menu", callback_data="main_menu:show_start_menu_from_my_requests")
    )

    keyboard_to_show = final_keyboard_builder.as_markup()
    final_text_object = as_list(*page_content_elements, sep="\n") if page_content_elements else Text(
        "🤷 no requests to display.")
    text_to_send = final_text_object.as_markdown()

    try:
        if is_callback:
            await bot.edit_message_text(
                text=text_to_send, chat_id=chat_id, message_id=original_message_id,
                reply_markup=keyboard_to_show, parse_mode="MarkdownV2",
            )
        else:
            await bot.send_message(
                chat_id=chat_id, text=text_to_send, reply_markup=keyboard_to_show, parse_mode="MarkdownV2"
            )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug("message not modified for my_requests page %s, user %s.", page, user_id)
        else:
            logger.error("telegram badrequest in _send_my_requests_page_logic: %s", e)
            if is_callback and chat_id:
                error_reply_obj = Text("❗could not update the request list.")
                await bot.send_message(chat_id, error_reply_obj.as_markdown(), parse_mode="MarkdownV2",
                                       reply_markup=keyboard_to_show)
    except Exception as e:
        logger.error("exception in _send_my_requests_page_logic: %s", e)
        if is_callback and chat_id:
            error_reply_obj = Text("❗an error occurred.")
            await bot.send_message(chat_id, error_reply_obj.as_markdown(), parse_mode="MarkdownV2",
                                   reply_markup=keyboard_to_show)
