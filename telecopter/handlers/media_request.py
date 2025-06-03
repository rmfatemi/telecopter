from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

import telecopter.tmdb as tmdb_api
from telecopter.logger import setup_logger
from telecopter.handlers.handler_states import RequestMediaStates
from telecopter.utils import truncate_text, format_media_details_for_user


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
    builder.button(text="📝 other / not found - manual request", callback_data="tmdb_sel:manual_request")
    builder.button(text="❌ cancel request", callback_data="action_cancel")
    builder.adjust(1)
    return builder.as_markup()


@media_search_router.message(StateFilter(RequestMediaStates.typing_media_name), F.text)
async def process_media_name_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        await message.answer("✍️ please type the name of the media you're looking for.")
        return

    query_text = message.text.strip()
    if not query_text or len(query_text) < 2:
        await message.answer("✍️ your search query is too short. please try a more specific name.")
        return

    logger.info("user %s initiated media search with query: %s", message.from_user.id, query_text)
    await state.update_data(request_query=query_text)
    searching_msg = await message.answer(f'🔎 searching for "{query_text}"...')

    search_results = await tmdb_api.search_media(query_text)
    try:
        await bot.delete_message(chat_id=searching_msg.chat.id, message_id=searching_msg.message_id)
    except Exception:
        logger.debug("could not delete 'searching...' message.")

    if not search_results:
        await message.answer(
            f'😕 sorry, i couldn\'t find any results for "{query_text}".\n'
            "you can try a different name, or choose 'other / not found'.",
            reply_markup=get_tmdb_select_keyboard([]),
        )
        await state.set_state(RequestMediaStates.select_media)
        return

    await message.answer(
        f'🔍 here\'s what i found for "{query_text}". please select one:',
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
        await callback_query.message.edit_text(
            "✍️ okay, you chose 'other / not found'.\n"
            "please describe the media you're looking for (e.g., title, year, any details). "
            f'your original search term was: "{original_query}".\nthis will be sent as a manual request.',
            reply_markup=None,
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
        await callback_query.message.edit_text(
            "❗ oops! an error occurred. please try searching again.", reply_markup=None
        )
        await state.set_state(RequestMediaStates.typing_media_name)
        return

    media_details = await tmdb_api.get_media_details(tmdb_id, media_type)
    if not media_details:
        await callback_query.message.edit_text(
            "🔎❗ sorry, i couldn't fetch details. please try another selection or search again.",
            reply_markup=None,
        )
        await state.set_state(RequestMediaStates.select_media)
        return

    await state.update_data(selected_media_details=media_details)
    formatted_details_obj = format_media_details_for_user(media_details)
    caption_text_md = formatted_details_obj.as_markdown() + "\n\n🎯 confirm: do you want to request this?"
    keyboard = get_request_confirm_keyboard()

    try:
        if callback_query.message:
            original_message_chat_id = callback_query.message.chat.id
            await callback_query.message.delete()

            if media_details.get("poster_url"):
                await bot.send_photo(
                    chat_id=original_message_chat_id,
                    photo=media_details["poster_url"],
                    caption=caption_text_md,
                    reply_markup=keyboard,
                    parse_mode="MarkdownV2",
                )
            else:
                await bot.send_message(
                    chat_id=original_message_chat_id,
                    text=caption_text_md,
                    reply_markup=keyboard,
                    parse_mode="MarkdownV2",
                )
    except Exception as e:
        logger.warning(f"error sending media confirmation: {e}. falling back.")
        await bot.send_message(
            chat_id=callback_query.from_user.id,
            text=caption_text_md,
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
        )
    await state.set_state(RequestMediaStates.confirm_media)
