from typing import Union

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.formatting import Text
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup

from telecopter.logger import setup_logger
from telecopter.handlers.common_utils import is_admin
from telecopter.constants import (
    TITLE_ADMIN_PANEL,
    BTN_VIEW_TASKS,
    BTN_SEND_ANNOUNCEMENT,
    MSG_ACCESS_DENIED,
    MSG_NOT_AUTHORIZED_ALERT,
    CALLBACK_ADMIN_PANEL_PREFIX,
    CALLBACK_ADMIN_PANEL_VIEW_TASKS,
    CALLBACK_ADMIN_PANEL_SEND_ANNOUNCEMENT,
)

logger = setup_logger(__name__)

admin_panel_router = Router(name="admin_panel_router")


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_VIEW_TASKS, callback_data=f"{CALLBACK_ADMIN_PANEL_PREFIX}:{CALLBACK_ADMIN_PANEL_VIEW_TASKS}"
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


@admin_panel_router.message(Command("admin"))
async def show_admin_panel_command(message: Message, bot: Bot):
    await show_admin_panel(message, bot)


@admin_panel_router.callback_query(F.data == f"{CALLBACK_ADMIN_PANEL_PREFIX}:{CALLBACK_ADMIN_PANEL_VIEW_TASKS}")
async def admin_panel_view_tasks_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    from .admin_tasks import list_admin_tasks

    if not callback_query.from_user or not await is_admin(callback_query.from_user.id):
        await callback_query.answer(MSG_NOT_AUTHORIZED_ALERT, show_alert=True)
        return
    await callback_query.answer()
    if callback_query.message and callback_query.from_user:
        await list_admin_tasks(
            message_to_edit=callback_query.message,
            acting_user_id=callback_query.from_user.id,
            bot=bot,
            state=state,
            page=1,
        )


@admin_panel_router.callback_query(F.data == f"{CALLBACK_ADMIN_PANEL_PREFIX}:{CALLBACK_ADMIN_PANEL_SEND_ANNOUNCEMENT}")
async def admin_panel_send_announcement_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    from .admin_announce import ask_announcement_type

    if not callback_query.from_user or not await is_admin(callback_query.from_user.id):
        await callback_query.answer(MSG_NOT_AUTHORIZED_ALERT, show_alert=True)
        return
    await callback_query.answer()
    if callback_query.message:
        await ask_announcement_type(callback_query.message, state, bot)
