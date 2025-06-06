from typing import Optional, Union

from aiogram import Bot
from aiogram.utils.formatting import Text
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton, InlineKeyboardMarkup

from telecopter.logger import setup_logger
from telecopter.handlers.common_utils import is_admin
from telecopter.constants import (
    TITLE_ADMIN_PANEL,
    BTN_VIEW_TASKS,
    BTN_MANAGE_PENDING_USERS,
    BTN_SEND_ANNOUNCEMENT,
    MSG_ACCESS_DENIED,
    MSG_NOT_AUTHORIZED_ALERT,
    CALLBACK_ADMIN_PANEL_PREFIX,
    CALLBACK_ADMIN_PANEL_VIEW_TASKS,
    CALLBACK_ADMIN_PANEL_MANAGE_USERS,
    CALLBACK_ADMIN_PANEL_SEND_ANNOUNCEMENT,
    MSG_MAIN_MENU_DEFAULT_WELCOME,
    BTN_REQUEST_MEDIA,
    BTN_MY_REQUESTS,
    BTN_REPORT_PROBLEM,
    BTN_CANCEL_ACTION,
)


logger = setup_logger(__name__)


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_VIEW_TASKS, callback_data=f"{CALLBACK_ADMIN_PANEL_PREFIX}:{CALLBACK_ADMIN_PANEL_VIEW_TASKS}"
    )
    builder.button(
        text=BTN_MANAGE_PENDING_USERS,
        callback_data=f"{CALLBACK_ADMIN_PANEL_PREFIX}:{CALLBACK_ADMIN_PANEL_MANAGE_USERS}",
    )
    builder.button(
        text=BTN_SEND_ANNOUNCEMENT,
        callback_data=f"{CALLBACK_ADMIN_PANEL_PREFIX}:{CALLBACK_ADMIN_PANEL_SEND_ANNOUNCEMENT}",
    )
    builder.adjust(1)
    return builder.as_markup()


async def show_admin_panel(event: Union[Message, CallbackQuery], bot: Bot):
    if not event.from_user or not await is_admin(event.from_user.id):
        if isinstance(event, Message):
            text_obj = Text(MSG_ACCESS_DENIED)
            await event.reply(text_obj.as_markdown(), parse_mode="MarkdownV2")
        elif isinstance(event, CallbackQuery):
            await event.answer(MSG_NOT_AUTHORIZED_ALERT, show_alert=True)
        return

    reply_markup = get_admin_panel_keyboard()
    text_obj = Text(TITLE_ADMIN_PANEL)

    if isinstance(event, Message) and event.chat:
        await event.answer(text_obj.as_markdown(), reply_markup=reply_markup, parse_mode="MarkdownV2")
    elif isinstance(event, CallbackQuery) and event.message:
        try:
            await event.message.edit_text(text_obj.as_markdown(), reply_markup=reply_markup, parse_mode="MarkdownV2")
            await event.answer()
        except Exception as e:
            logger.error("failed to edit message for admin panel: %s. sending new.", e)
            await event.answer()
            if event.message.chat:
                await bot.send_message(
                    event.message.chat.id, text_obj.as_markdown(), reply_markup=reply_markup, parse_mode="MarkdownV2"
                )


def get_user_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text=BTN_REQUEST_MEDIA, callback_data="main_menu:request_media"),
        InlineKeyboardButton(text=BTN_MY_REQUESTS, callback_data="main_menu:my_requests"),
        InlineKeyboardButton(text=BTN_REPORT_PROBLEM, callback_data="main_menu:report_problem"),
        InlineKeyboardButton(text=BTN_CANCEL_ACTION, callback_data="main_menu:cancel_current_action"),
    )
    builder.adjust(2, 2)
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
