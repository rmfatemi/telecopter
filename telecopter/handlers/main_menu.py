from typing import Optional, Union

from aiogram import Router, F, Bot
from aiogram.utils.formatting import Text
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton, InlineKeyboardMarkup

from telecopter.logger import setup_logger
from telecopter.handlers.core_commands import help_command_logic
from telecopter.handlers.handler_states import RequestMediaStates
from telecopter.handlers.common_utils import ensure_user_approved
from telecopter.constants import (
    MSG_MAIN_MENU_DEFAULT_WELCOME,
    MSG_MAIN_MENU_BACK_WELCOME,
    PROMPT_MAIN_MENU_REQUEST_MEDIA,
    MSG_MAIN_MENU_MEDIA_SEARCH_UNAVAILABLE,
    BTN_REQUEST_MEDIA,
    BTN_MY_REQUESTS,
    BTN_REPORT_PROBLEM,
    BTN_HELP,
    BTN_CANCEL_ACTION,
)

logger = setup_logger(__name__)

main_menu_router = Router(name="main_menu_router")


def get_user_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text=BTN_REQUEST_MEDIA, callback_data="main_menu:request_media"),
        InlineKeyboardButton(text=BTN_MY_REQUESTS, callback_data="main_menu:my_requests"),
        InlineKeyboardButton(text=BTN_REPORT_PROBLEM, callback_data="main_menu:report_problem"),
        InlineKeyboardButton(text=BTN_HELP, callback_data="main_menu:show_help"),
        InlineKeyboardButton(text=BTN_CANCEL_ACTION, callback_data="main_menu:cancel_current_action"),
    )
    builder.adjust(2, 2, 1)
    return builder.as_markup()


async def show_main_menu_for_user(
    event: Union[Message, CallbackQuery],
    bot: Bot,
    custom_text_str: Optional[str] = None,
    custom_text_md: Optional[str] = None,
    custom_text_html: Optional[str] = None,
    custom_text_obj: Optional[Text] = None,
):
    user_first_name = event.from_user.first_name if event.from_user else "there"
    reply_markup = get_user_main_menu_keyboard()

    text_to_send: str
    parse_mode_to_use: Optional[str] = "MarkdownV2"

    if custom_text_obj:
        text_to_send = custom_text_obj.as_markdown()
    elif custom_text_html:
        text_to_send = custom_text_html
        parse_mode_to_use = "HTML"
    elif custom_text_md:
        text_to_send = custom_text_md
    elif custom_text_str:
        text_to_send = Text(custom_text_str).as_markdown()
    else:
        text_to_send = Text(MSG_MAIN_MENU_DEFAULT_WELCOME.format(user_first_name=user_first_name)).as_markdown()

    if isinstance(event, Message) and event.chat:
        await bot.send_message(event.chat.id, text_to_send, reply_markup=reply_markup, parse_mode=parse_mode_to_use)
    elif isinstance(event, CallbackQuery) and event.message:
        try:
            await event.message.edit_text(text_to_send, reply_markup=reply_markup, parse_mode=parse_mode_to_use)
            await event.answer()
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await event.answer()
            else:
                logger.warning("could not edit message to show main menu: %s. sending new.", e)
                await event.answer()
                if event.message.chat:
                    await bot.send_message(
                        event.message.chat.id, text_to_send, reply_markup=reply_markup, parse_mode=parse_mode_to_use
                    )


@main_menu_router.callback_query(F.data == "main_menu:show_help")
async def main_menu_help_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message:
        return
    await help_command_logic(callback_query, state, bot, callback_query.from_user.id)


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
    await callback_query.message.edit_text(text_obj.as_markdown(), reply_markup=None, parse_mode="MarkdownV2")
    await state.set_state(RequestMediaStates.typing_media_name)


@main_menu_router.callback_query(F.data == "main_menu:my_requests")
async def main_menu_my_requests_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    from .request_history import my_requests_entrypoint

    if not callback_query.message or not callback_query.from_user:
        return
    if not await ensure_user_approved(callback_query, bot, state):
        return
    await callback_query.answer()
    await my_requests_entrypoint(callback_query.message, bot, state, is_callback=True)


@main_menu_router.callback_query(F.data == "main_menu:report_problem")
async def main_menu_report_problem_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    from .problem_report import report_command_entry_handler

    if not callback_query.message or not callback_query.from_user:
        return

    await callback_query.answer()
    await report_command_entry_handler(callback_query.message, state, bot, is_triggered_by_command=False)


@main_menu_router.callback_query(F.data == "main_menu:show_start_menu_from_my_requests")
async def handle_back_to_main_menu_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message:
        return
    if not await ensure_user_approved(callback_query, bot, state):
        return

    welcome_text_obj = Text(MSG_MAIN_MENU_BACK_WELCOME.format(user_first_name=callback_query.from_user.first_name))
    await show_main_menu_for_user(callback_query, bot, custom_text_obj=welcome_text_obj)
