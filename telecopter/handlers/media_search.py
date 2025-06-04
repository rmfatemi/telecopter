from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.utils.formatting import Text
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

import telecopter.tmdb as tmdb_api
from telecopter.logger import setup_logger
from telecopter.handlers.handler_states import RequestMediaStates
from telecopter.utils import truncate_text, format_media_details_for_user
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
)


logger = setup_logger(__name__)

media_search_router = Router(name="media_search_router")


def get_tmdb_select_keyboard(search_results: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in search_results:
        year = f" ({item['year']})" if item.get("year") else ""
        media_emoji = "🎬" if item["media_type"] == "movie" else "📺" if item["media_type"] == "tv" else "❔"
        button_text = f"{media_emoji} {item['title']}{year}"
        callback_data = f"tmdb_sel:{item['tmdb_id']}:{item['media_type']}"
        builder.button(text=truncate_text(button_text, 60), callback_data=callback_data)
    builder.button(text=BTN_MEDIA_MANUAL_REQUEST, callback_data="tmdb_sel:manual_request")
    builder.button(text=BTN_CANCEL_ACTION, callback_data="action_cancel")
    builder.adjust(1)
    return builder.as_markup()


@media_search_router.message(StateFilter(RequestMediaStates.typing_media_name), F.text)
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


@media_search_router.callback_query(StateFilter(RequestMediaStates.select_media), F.data.startswith("tmdb_sel:"))
async def select_media_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    from telecopter.handlers.media_submission import get_request_confirm_keyboard

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
