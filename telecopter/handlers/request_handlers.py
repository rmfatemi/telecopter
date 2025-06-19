from typing import Optional, List, Union

from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.formatting import Text, Bold, Italic, Code, as_list
from aiogram.utils.keyboard import InlineKeyboardBuilder

import telecopter.tmdb as tmdb_api
import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import DEFAULT_PAGE_SIZE, MAX_NOTE_LENGTH
from telecopter.handlers.handler_states import RequestMediaStates
from telecopter.handlers.menu_utils import show_main_menu_for_user
from telecopter.handlers.common_utils import notify_admin_formatted
from telecopter.utils import truncate_text, format_media_details_for_user, format_request_for_admin, format_request_item_display_parts
from telecopter.handlers.admin_handlers import get_admin_request_action_keyboard
from telecopter.constants import (
    PROMPT_MEDIA_NAME_TYPING,
    ERR_MEDIA_QUERY_TOO_SHORT,
    MSG_MEDIA_SEARCHING,
    MSG_MEDIA_NO_RESULTS,
    MSG_MEDIA_RESULTS_FOUND,
    PROMPT_MANUAL_REQUEST_DESCRIPTION,
    ERR_CALLBACK_INVALID_MEDIA_SELECTION,
    ERR_MEDIA_DETAILS_FETCH_FAILED,
    MSG_MEDIA_CONFIRM_REQUEST,
    BTN_MEDIA_MANUAL_REQUEST,
    BTN_CANCEL_ACTION,
    GenericCallbackAction,
    BTN_CONFIRM_REQUEST,
    BTN_CONFIRM_WITH_NOTE,
    PROMPT_MANUAL_REQUEST,
    ERR_MANUAL_REQUEST_TOO_SHORT,
    MSG_MANUAL_REQUEST_SUBMITTED,
    MSG_MANUAL_REQUEST_SUCCESS,
    ERR_REQUEST_EXPIRED,
    MSG_SELECTION_EXPIRED,
    PROMPT_REQUEST_NOTE,
    MSG_REQUEST_SUBMITTED,
    MSG_REQUEST_WITH_NOTE_SUBMITTED,
    MSG_REQUEST_SUCCESS,
    RequestConfirmAction,
    MediaType,
    BTN_PREVIOUS_PAGE,
    BTN_NEXT_PAGE,
    BTN_BACK_TO_MAIN_MENU,
    MSG_NO_REQUESTS_YET,
    MSG_NO_MORE_REQUESTS,
    MSG_REQUESTS_PAGE_HEADER,
    MSG_ITEM_MESSAGE_DIVIDER,
    MainMenuCallback,
)

logger = setup_logger(__name__)

request_router = Router(name="request_router")


# --- Media Search and Submission Logic ---

def get_tmdb_select_keyboard(search_results: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in search_results:
        year = f" ({item['year']})" if item.get("year") else ""
        media_emoji = "🎬" if item["media_type"] == "movie" else "📺" if item["media_type"] == "tv" else "❔"
        button_text = f"{media_emoji} {item['title']}{year}"
        callback_data = f"tmdb_sel:{item['tmdb_id']}:{item['media_type']}"
        builder.button(text=truncate_text(button_text, 60), callback_data=callback_data)
    builder.button(text=BTN_MEDIA_MANUAL_REQUEST, callback_data="tmdb_sel:manual_request")
    builder.button(text=BTN_CANCEL_ACTION, callback_data=GenericCallbackAction.CANCEL.value)
    builder.adjust(1)
    return builder.as_markup()

def get_request_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_CONFIRM_REQUEST, callback_data=f"req_conf:{RequestConfirmAction.YES.value}")
    builder.button(text=BTN_CONFIRM_WITH_NOTE, callback_data=f"req_conf:{RequestConfirmAction.YES_WITH_NOTE.value}")
    builder.button(text=BTN_CANCEL_ACTION, callback_data=GenericCallbackAction.CANCEL.value)
    builder.adjust(1)
    return builder.as_markup()

@request_router.message(StateFilter(RequestMediaStates.typing_media_name), F.text)
async def process_media_name_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        reply_text_obj = Text(PROMPT_MEDIA_NAME_TYPING)
        await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    query_text = message.text.strip()
    if not query_text or len(query_text) < 2:
        reply_text_obj = Text(ERR_MEDIA_QUERY_TOO_SHORT)
        await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    logger.info("user %s initiated media search with query: %s", message.from_user.id, query_text)
    await state.update_data(request_query=query_text)
    searching_msg_obj = Text(MSG_MEDIA_SEARCHING.format(query_text=query_text))
    searching_msg = await message.answer(searching_msg_obj.as_markdown(), parse_mode="MarkdownV2")

    search_results = await tmdb_api.search_media(query_text)
    try:
        if searching_msg:
            await bot.delete_message(chat_id=searching_msg.chat.id, message_id=searching_msg.message_id)
    except Exception:
        logger.debug("could not delete 'searching...' message.")

    if not search_results:
        reply_text_obj = Text(MSG_MEDIA_NO_RESULTS.format(query_text=query_text))
        await message.answer(
            reply_text_obj.as_markdown(),
            parse_mode="MarkdownV2",
            reply_markup=get_tmdb_select_keyboard([]),
        )
        await state.set_state(RequestMediaStates.select_media)
        return

    reply_text_obj = Text(MSG_MEDIA_RESULTS_FOUND.format(query_text=query_text))
    await message.answer(
        reply_text_obj.as_markdown(),
        parse_mode="MarkdownV2",
        reply_markup=get_tmdb_select_keyboard(search_results),
    )
    await state.set_state(RequestMediaStates.select_media)

@request_router.callback_query(StateFilter(RequestMediaStates.select_media), F.data.startswith("tmdb_sel:"))
async def select_media_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message:
        return

    action_data = callback_query.data

    if action_data == "tmdb_sel:manual_request":
        user_fsm_data = await state.get_data()
        original_query = user_fsm_data.get("request_query", "your previous search")
        prompt_text_obj = Text(PROMPT_MANUAL_REQUEST_DESCRIPTION.format(original_query=original_query))
        await callback_query.message.edit_text(
            prompt_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None
        )
        await state.set_state(RequestMediaStates.typing_manual_request_description)
        return

    tmdb_id_str: str
    media_type: str
    try:
        _, tmdb_id_str, media_type = action_data.split(":", 2)
        tmdb_id = int(tmdb_id_str)
    except ValueError:
        logger.error("invalid callback data for tmdb selection: %s", action_data)
        error_text_obj = Text(ERR_CALLBACK_INVALID_MEDIA_SELECTION)
        await callback_query.message.edit_text(error_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None)
        await state.set_state(RequestMediaStates.typing_media_name)
        return

    media_details = await tmdb_api.get_media_details(tmdb_id, media_type)
    if not media_details:
        error_text_obj = Text(ERR_MEDIA_DETAILS_FETCH_FAILED)
        await callback_query.message.edit_text(error_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None)
        await state.set_state(RequestMediaStates.select_media)
        return

    await state.update_data(selected_media_details=media_details)
    formatted_details_obj = format_media_details_for_user(media_details)

    caption_confirm_text_obj = Text(MSG_MEDIA_CONFIRM_REQUEST)
    full_caption_obj = Text(formatted_details_obj, "\n\n", caption_confirm_text_obj)

    keyboard = get_request_confirm_keyboard()

    try:
        if callback_query.message:
            original_message_chat_id = callback_query.message.chat.id
            await callback_query.message.delete()

            if media_details.get("poster_url"):
                await bot.send_photo(
                    chat_id=original_message_chat_id,
                    photo=media_details["poster_url"],
                    caption=full_caption_obj.as_markdown(),
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
            else:
                await bot.send_message(
                    chat_id=original_message_chat_id,
                    text=full_caption_obj.as_markdown(),
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
    except Exception as e:
        logger.warning(f"error sending media confirmation: {e}. falling back.")
        if callback_query.message and callback_query.from_user:
            await bot.send_message(
                chat_id=callback_query.from_user.id,
                text=full_caption_obj.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
    await state.set_state(RequestMediaStates.confirm_media)

@request_router.message(StateFilter(RequestMediaStates.typing_manual_request_description), F.text)
async def manual_request_description_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        reply_text_obj = Text(PROMPT_MANUAL_REQUEST)
        await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    description = message.text.strip()
    if len(description) < 5:
        reply_text_obj = Text(ERR_MANUAL_REQUEST_TOO_SHORT)
        await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    user_fsm_data = await state.get_data()
    original_query = user_fsm_data.get("request_query", "not specified")

    request_id = await db.add_media_request(
        user_id=message.from_user.id,
        tmdb_id=None,
        title=description,
        year=None,
        imdb_id=None,
        request_type=MediaType.MANUAL.value,
        user_query=original_query,
        user_note=None,
    )
    reply_text_obj = Text(MSG_MANUAL_REQUEST_SUBMITTED.format(description=truncate_text(description, 50)))
    await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(message.from_user.id)
    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_kb = get_admin_request_action_keyboard(request_id)
        await notify_admin_formatted(bot, admin_msg_obj, admin_kb)

    await state.clear()
    await show_main_menu_for_user(message, bot, custom_text_str=MSG_MANUAL_REQUEST_SUCCESS)

@request_router.callback_query(StateFilter(RequestMediaStates.confirm_media), F.data.startswith("req_conf:"))
async def confirm_media_request_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message:
        return

    action = callback_query.data.split(":")[1]
    user_fsm_data = await state.get_data()
    selected_media = user_fsm_data.get("selected_media_details")
    chat_id_to_reply = callback_query.from_user.id

    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug("confirmation message not modified (buttons already removed or never existed).")
        elif "message can't be edited" in str(e).lower():
            logger.warning(
                f"Failed to edit reply markup for message {callback_query.message.message_id}: {e}. Message might be"
                " too old or not editable."
            )
        else:
            logger.error(f"TelegramBadRequest when editing confirmation message markup: {e}")
    except Exception as e:
        logger.error(f"Unexpected error when editing confirmation message markup: {e}")

    if not selected_media:
        error_text_obj = Text(ERR_REQUEST_EXPIRED)
        await bot.send_message(chat_id_to_reply, error_text_obj.as_markdown(), parse_mode="MarkdownV2")
        await state.clear()
        await show_main_menu_for_user(callback_query, bot, custom_text_str=MSG_SELECTION_EXPIRED)
        return

    if action == RequestConfirmAction.YES_WITH_NOTE.value:
        prompt_text_obj = Text(PROMPT_REQUEST_NOTE)
        await bot.send_message(chat_id_to_reply, prompt_text_obj.as_markdown(), parse_mode="MarkdownV2")
        await state.set_state(RequestMediaStates.typing_user_note)
        return

    request_id = await db.add_media_request(
        user_id=callback_query.from_user.id,
        tmdb_id=selected_media["tmdb_id"],
        title=selected_media["title"],
        year=selected_media.get("year"),
        imdb_id=selected_media.get("imdb_id"),
        request_type=selected_media["media_type"],
        user_query=user_fsm_data.get("request_query"),
        user_note=None,
    )
    reply_text_obj = Text(MSG_REQUEST_SUBMITTED)
    await bot.send_message(chat_id_to_reply, reply_text_obj.as_markdown(), parse_mode="MarkdownV2")

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(callback_query.from_user.id)
    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_kb = get_admin_request_action_keyboard(request_id)
        await notify_admin_formatted(bot, admin_msg_obj, admin_kb)

    await state.clear()
    await show_main_menu_for_user(callback_query, bot, custom_text_str=MSG_REQUEST_SUCCESS)

@request_router.message(StateFilter(RequestMediaStates.typing_user_note), F.text)
async def user_note_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        return

    user_fsm_data = await state.get_data()
    selected_media = user_fsm_data.get("selected_media_details")

    if not selected_media:
        error_text_obj = Text(ERR_REQUEST_EXPIRED)
        await message.answer(error_text_obj.as_markdown(), parse_mode="MarkdownV2")
        await state.clear()
        await show_main_menu_for_user(message, bot, custom_text_str=MSG_SELECTION_EXPIRED)
        return

    note_text = truncate_text(message.text, MAX_NOTE_LENGTH)
    request_id = await db.add_media_request(
        user_id=message.from_user.id,
        tmdb_id=selected_media["tmdb_id"],
        title=selected_media["title"],
        year=selected_media.get("year"),
        imdb_id=selected_media.get("imdb_id"),
        request_type=selected_media["media_type"],
        user_query=user_fsm_data.get("request_query"),
        user_note=note_text,
    )
    reply_text_obj = Text(MSG_REQUEST_WITH_NOTE_SUBMITTED)
    await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(message.from_user.id)
    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_kb = get_admin_request_action_keyboard(request_id)
        await notify_admin_formatted(bot, admin_msg_obj, admin_kb)

    await state.clear()
    await show_main_menu_for_user(message, bot, custom_text_str=MSG_REQUEST_SUCCESS)


# --- Request History Logic ---

def get_my_requests_pagination_keyboard(page: int, total_pages: int) -> Optional[InlineKeyboardMarkup]:
    builder = InlineKeyboardBuilder()

    if page > 1:
        builder.button(text=BTN_PREVIOUS_PAGE, callback_data=f"my_req_page:{page - 1}")
    if page < total_pages:
        builder.button(text=BTN_NEXT_PAGE, callback_data=f"my_req_page:{page + 1}")

    added_buttons_list = list(builder.buttons)
    num_added_buttons = len(added_buttons_list)

    if num_added_buttons > 0:
        builder.adjust(2 if num_added_buttons > 1 else 1)
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

@request_router.callback_query(F.data.startswith("my_req_page:"))
async def my_requests_page_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message:
        return
    page = 1
    try:
        page_str = callback_query.data.split(":")[1]
        page = int(page_str)
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

    logger.debug(f"fetching requests for user_id: {user_id}, page: {page}")
    requests_rows = await db.get_user_requests(user_id, page, DEFAULT_PAGE_SIZE)
    total_requests = await db.get_user_requests_count(user_id)
    logger.debug(
        f"found {len(requests_rows)} rows for this page, total_requests: {total_requests} for user_id: {user_id}"
    )

    total_pages = (total_requests + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
    total_pages = max(1, total_pages)

    page_content_elements: List[Union[Text, Bold, Italic, Code]] = []
    final_keyboard_builder = InlineKeyboardBuilder()

    if not requests_rows and page == 1:
        page_content_elements.append(Text(MSG_NO_REQUESTS_YET))
    elif not requests_rows and page > 1:
        page_content_elements.append(Text(MSG_NO_MORE_REQUESTS.format(page=page)))
    else:
        page_content_elements.append(Bold(MSG_REQUESTS_PAGE_HEADER.format(page=page, total_pages=total_pages)))
        if requests_rows:
            page_content_elements.append(Text("\n"))

        for req_row in requests_rows:
            req = dict(req_row)

            current_item_display_parts = format_request_item_display_parts(req, view_context="user_history_item")

            if current_item_display_parts:
                page_content_elements.append(as_list(*current_item_display_parts, sep=""))
                page_content_elements.append(Text(MSG_ITEM_MESSAGE_DIVIDER))

    if (
        page_content_elements
        and isinstance(page_content_elements[-1], Text)
        and page_content_elements[-1].render()[0] == MSG_ITEM_MESSAGE_DIVIDER
    ):
        page_content_elements.pop()

    pagination_kb = get_my_requests_pagination_keyboard(page, total_pages)
    if pagination_kb:
        for row_buttons in pagination_kb.inline_keyboard:
            final_keyboard_builder.row(*row_buttons)

    final_keyboard_builder.row(
        InlineKeyboardButton(
            text=BTN_BACK_TO_MAIN_MENU,
            callback_data=f"main_menu:{MainMenuCallback.SHOW_START_MENU_FROM_MY_REQUESTS.value}",
        )
    )
    keyboard_to_show = final_keyboard_builder.as_markup()

    if not requests_rows:
        if page_content_elements:
            final_text_object = page_content_elements[0]
        else:
            final_text_object = Text(MSG_NO_REQUESTS_YET)
    else:
        final_text_object = as_list(*page_content_elements, sep="\n")

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
            logger.error("telegram badrequest in _send_my_requests_page_logic for user %s: %s", user_id, e)
    except Exception as e:
        logger.error("exception in _send_my_requests_page_logic for user %s: %s", user_id, e)
