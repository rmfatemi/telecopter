from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.utils.formatting import Text
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

from telecopter.logger import setup_logger
from telecopter.handlers.common_utils import ensure_user_approved
from telecopter.handlers.menu_utils import show_main_menu_for_user
from telecopter.handlers.handler_states import RequestMediaStates, ReportProblemStates
from telecopter.constants import (
    MSG_MAIN_MENU_BACK_WELCOME,
    PROMPT_MAIN_MENU_REQUEST_MEDIA,
    MSG_MAIN_MENU_MEDIA_SEARCH_UNAVAILABLE,
    PROMPT_PROBLEM_DESCRIPTION,
    BTN_CANCEL_ACTION,
    CALLBACK_ACTION_CANCEL,
)


logger = setup_logger(__name__)

main_menu_router = Router(name="main_menu_router")


@main_menu_router.callback_query(F.data == "main_menu:request_media")
async def main_menu_request_media_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if not callback_query.message or not callback_query.from_user:
        return
    if not await ensure_user_approved(callback_query, bot, state):
        return
    await callback_query.answer()

    from telecopter.config import TMDB_API_KEY

    if not TMDB_API_KEY:
        text_obj = Text(MSG_MAIN_MENU_MEDIA_SEARCH_UNAVAILABLE)
        await callback_query.message.edit_text(text_obj.as_markdown(), reply_markup=None, parse_mode="MarkdownV2")
        return

    text_obj = Text(PROMPT_MAIN_MENU_REQUEST_MEDIA)
    cancel_kb_builder = InlineKeyboardBuilder()
    cancel_kb_builder.button(text=BTN_CANCEL_ACTION, callback_data=CALLBACK_ACTION_CANCEL)
    try:
        await callback_query.message.edit_text(
            text_obj.as_markdown(), reply_markup=cancel_kb_builder.as_markup(), parse_mode="MarkdownV2"
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            pass
        else:
            logger.warning(f"Could not edit message for request media: {e}. Sending new.")
            if callback_query.message and callback_query.message.chat:
                await bot.send_message(
                    chat_id=callback_query.message.chat.id,
                    text=text_obj.as_markdown(),
                    reply_markup=cancel_kb_builder.as_markup(),
                    parse_mode="MarkdownV2",
                )
    await state.set_state(RequestMediaStates.typing_media_name)


@main_menu_router.callback_query(F.data == "main_menu:my_requests")
async def main_menu_my_requests_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    from .request_history import my_requests_entrypoint

    if not callback_query.message or not callback_query.from_user:
        return
    if not await ensure_user_approved(callback_query, bot, state):
        return
    await callback_query.answer()

    await my_requests_entrypoint(
        base_message=callback_query.message,
        requesting_user_id=callback_query.from_user.id,
        bot=bot,
        state=state,
        is_callback=True,
    )


@main_menu_router.callback_query(F.data == "main_menu:report_problem")
async def main_menu_report_problem_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if not callback_query.message or not callback_query.from_user:
        return

    if not await ensure_user_approved(callback_query, bot, state):
        return

    await callback_query.answer()

    text_obj = Text(PROMPT_PROBLEM_DESCRIPTION)
    cancel_kb_builder = InlineKeyboardBuilder()
    cancel_kb_builder.button(text=BTN_CANCEL_ACTION, callback_data=CALLBACK_ACTION_CANCEL)

    try:
        await callback_query.message.edit_text(
            text_obj.as_markdown(), reply_markup=cancel_kb_builder.as_markup(), parse_mode="MarkdownV2"
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            pass
        else:
            logger.warning(f"Could not edit message for report problem: {e}. Sending new.")
            if callback_query.message and callback_query.message.chat:
                await bot.send_message(
                    chat_id=callback_query.message.chat.id,
                    text=text_obj.as_markdown(),
                    reply_markup=cancel_kb_builder.as_markup(),
                    parse_mode="MarkdownV2",
                )

    await state.set_state(ReportProblemStates.typing_problem)


@main_menu_router.callback_query(F.data == "main_menu:show_start_menu_from_my_requests")
async def handle_back_to_main_menu_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message:
        return
    if not await ensure_user_approved(callback_query, bot, state):
        return

    welcome_text_obj = Text(MSG_MAIN_MENU_BACK_WELCOME.format(user_first_name=callback_query.from_user.first_name))
    await show_main_menu_for_user(callback_query, bot, custom_text_obj=welcome_text_obj)
