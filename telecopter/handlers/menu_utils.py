from typing import Union

from aiogram import Bot
from aiogram.utils.formatting import Text
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from telecopter.logger import setup_logger
from telecopter.handlers.common_utils import is_admin
from telecopter.constants import (
    TITLE_ADMIN_PANEL,
    BTN_VIEW_TASKS,
    BTN_MANAGE_PENDING_USERS,
    BTN_SEND_BROADCASTMENT,
    AdminPanelCallback,
    MSG_MAIN_MENU_DEFAULT_WELCOME,
    BTN_REQUEST_MEDIA,
    BTN_MY_REQUESTS,
    BTN_REPORT_PROBLEM,
    MainMenuCallback,
    MSG_ADMIN_ONLY_ACTION,
)


logger = setup_logger(__name__)


async def show_admin_panel(event: Union[Message, CallbackQuery], bot: Bot):
    if not event.from_user or not await is_admin(event.from_user.id):
        if isinstance(event, Message):
            await event.reply(MSG_ADMIN_ONLY_ACTION)
        elif isinstance(event, CallbackQuery):
            await event.answer(MSG_ADMIN_ONLY_ACTION, show_alert=True)
        return

    admin_keyboard = (
        InlineKeyboardBuilder()
        .button(text=BTN_VIEW_TASKS, callback_data=f"{AdminPanelCallback.PREFIX.value}:{AdminPanelCallback.VIEW_TASKS.value}")
        .button(
            text=BTN_MANAGE_PENDING_USERS,
            callback_data=f"{AdminPanelCallback.PREFIX.value}:{AdminPanelCallback.MANAGE_USERS.value}",
        )
        .button(
            text=BTN_SEND_BROADCASTMENT,
            callback_data=f"{AdminPanelCallback.PREFIX.value}:{AdminPanelCallback.SEND_BROADCASTMENT.value}",
        )
        .adjust(1)
        .as_markup()
    )
    text_obj = Text(TITLE_ADMIN_PANEL)

    message_to_edit = event.message if isinstance(event, CallbackQuery) else event
    try:
        await message_to_edit.edit_text(
            text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=admin_keyboard
        )
    except Exception:
        await bot.send_message(
            event.from_user.id, text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=admin_keyboard
        )

async def show_main_menu_for_user(
    event: Union[Message, CallbackQuery], bot: Bot, custom_text_str: str | None = None
):
    user_first_name = event.from_user.first_name
    text_str = custom_text_str or MSG_MAIN_MENU_DEFAULT_WELCOME.format(user_first_name=user_first_name)
    text_obj = Text(text_str)

    menu_builder = InlineKeyboardBuilder()
    menu_builder.button(text=BTN_REQUEST_MEDIA, callback_data=f"{MainMenuCallback.PREFIX.value}:{MainMenuCallback.REQUEST_MEDIA.value}")
    menu_builder.button(text=BTN_MY_REQUESTS, callback_data=f"{MainMenuCallback.PREFIX.value}:{MainMenuCallback.MY_REQUESTS.value}")
    menu_builder.button(
        text=BTN_REPORT_PROBLEM, callback_data=f"{MainMenuCallback.PREFIX.value}:{MainMenuCallback.REPORT_PROBLEM.value}"
    )
    menu_builder.adjust(1)
    menu_markup = menu_builder.as_markup()

    if isinstance(event, CallbackQuery):
        message_to_handle = event.message
        try:
            await bot.delete_message(message_to_handle.chat.id, message_to_handle.message_id)
        except Exception as e:
            logger.debug(f"Could not delete message before showing main menu: {e}")
        await bot.send_message(
            message_to_handle.chat.id, text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=menu_markup
        )
    else:
        await event.answer(text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=menu_markup)
