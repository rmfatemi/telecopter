from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.utils.formatting import Text
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import MAX_NOTE_LENGTH
from telecopter.handlers.handler_states import RequestMediaStates
from telecopter.handlers.common_utils import notify_admin_formatted
from telecopter.utils import truncate_text, format_request_for_admin
from telecopter.handlers.admin_moderate import get_admin_request_action_keyboard


logger = setup_logger(__name__)

media_submission_router = Router(name="media_submission_router")


def get_request_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ yes, request it", callback_data="req_conf:yes")
    builder.button(text="📝 yes, with a note", callback_data="req_conf:yes_note")
    builder.button(text="❌ no, cancel", callback_data="action_cancel")
    builder.adjust(1)
    return builder.as_markup()


@media_submission_router.message(StateFilter(RequestMediaStates.typing_manual_request_description), F.text)
async def manual_request_description_handler(message: Message, state: FSMContext, bot: Bot):
    from telecopter.handlers.main_menu import show_main_menu_for_user

    if not message.from_user or not message.text:
        reply_text_obj = Text("✍️ please provide a description for your manual request.")
        await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    description = message.text.strip()
    if len(description) < 5:
        reply_text_obj = Text("✍️ your description is a bit short. please provide more details.")
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
        request_type="manual_media",
        user_query=original_query,
        user_note=None,
    )
    reply_text_str = (
        f'✅ your manual request for "{truncate_text(description, 50)}" has been submitted. admins will review it.'
    )
    reply_text_obj = Text(reply_text_str)
    await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(message.from_user.id)
    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_kb = get_admin_request_action_keyboard(request_id)
        await notify_admin_formatted(bot, admin_msg_obj, admin_kb)

    await state.clear()
    await show_main_menu_for_user(
        message, bot, custom_text_str="✅ manual request submitted! what can i help you with next?"
    )


@media_submission_router.callback_query(StateFilter(RequestMediaStates.confirm_media), F.data.startswith("req_conf:"))
async def confirm_media_request_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    from telecopter.handlers.main_menu import show_main_menu_for_user

    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message:
        return

    action = callback_query.data.split(":")[1]
    user_fsm_data = await state.get_data()
    selected_media = user_fsm_data.get("selected_media_details")
    chat_id_to_reply = callback_query.from_user.id

    try:
        await callback_query.message.delete()
    except Exception as e:
        logger.debug(f"failed to delete confirmation message: {e}")

    if not selected_media:
        error_text_obj = Text("⏳ error: your selection seems to have expired. please start over.")
        await bot.send_message(chat_id_to_reply, error_text_obj.as_markdown(), parse_mode="MarkdownV2")
        await state.clear()
        await show_main_menu_for_user(
            callback_query, bot, custom_text_str="⏳ selection expired. what can i help you with next?"
        )
        return

    if action == "yes_note":
        prompt_text_obj = Text("📝 please send a short note for your request.")
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
    reply_text_obj = Text("✅ your request has been submitted for review. you'll be notified!")
    await bot.send_message(chat_id_to_reply, reply_text_obj.as_markdown(), parse_mode="MarkdownV2")

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(callback_query.from_user.id)
    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_kb = get_admin_request_action_keyboard(request_id)
        await notify_admin_formatted(bot, admin_msg_obj, admin_kb)

    await state.clear()
    await show_main_menu_for_user(
        callback_query, bot, custom_text_str="✅ request submitted! what can i help you with next?"
    )


@media_submission_router.message(StateFilter(RequestMediaStates.typing_user_note), F.text)
async def user_note_handler(message: Message, state: FSMContext, bot: Bot):
    from telecopter.handlers.main_menu import show_main_menu_for_user

    if not message.from_user or not message.text:
        return

    user_fsm_data = await state.get_data()
    selected_media = user_fsm_data.get("selected_media_details")

    if not selected_media:
        error_text_obj = Text("⏳ error: your selection seems to have expired. please start the request over.")
        await message.answer(error_text_obj.as_markdown(), parse_mode="MarkdownV2")
        await state.clear()
        await show_main_menu_for_user(
            message, bot, custom_text_str="⏳ selection expired. what can i help you with next?"
        )
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
    reply_text_obj = Text("✅ your request with the note has been submitted. you'll be notified!")
    await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(message.from_user.id)
    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_kb = get_admin_request_action_keyboard(request_id)
        await notify_admin_formatted(bot, admin_msg_obj, admin_kb)

    await state.clear()
    await show_main_menu_for_user(message, bot, custom_text_str="✅ request submitted! what can i help you with next?")
