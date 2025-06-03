from typing import Union

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.utils.formatting import Text
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup

from telecopter.logger import setup_logger
from telecopter.handlers.common_utils import is_admin


logger = setup_logger(__name__)

admin_panel_router = Router(name="admin_panel_router")


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 view tasks", callback_data="admin_panel:view_tasks")
    builder.button(text="📢 send announcement", callback_data="admin_panel:send_announcement")
    builder.adjust(1)
    return builder.as_markup()

async def show_admin_panel(event: Union[Message, CallbackQuery], bot: Bot):
    if not event.from_user or not await is_admin(event.from_user.id, bot):
        denied_text_obj = Text("access denied.")
        if isinstance(event, Message) and event.chat:
            await bot.send_message(event.chat.id, denied_text_obj.as_markdown(), parse_mode="MarkdownV2")
        elif isinstance(event, CallbackQuery):
            await event.answer("not authorized", show_alert=True)
        return

    text_obj = Text("👑 admin panel")
    reply_markup = get_admin_panel_keyboard()

    if isinstance(event, Message) and event.chat:
        await event.answer(text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=reply_markup)
    elif isinstance(event, CallbackQuery) and event.message:
        try:
            await event.message.edit_text(text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=reply_markup)
        except Exception as e:
            logger.error("failed to edit message for admin panel: %s. sending new.", e)
            await event.answer()
            if event.message.chat:
                await bot.send_message(event.message.chat.id, text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=reply_markup)

@admin_panel_router.message(Command("admin"))
async def show_admin_panel_command(message: Message, bot: Bot):
    await show_admin_panel(message, bot)

@admin_panel_router.callback_query(F.data == "admin_panel:view_tasks")
async def admin_panel_view_tasks_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    from .admin_tasks import list_admin_tasks
    if not callback_query.from_user or not await is_admin(callback_query.from_user.id, bot):
        await callback_query.answer("access denied.", show_alert=True)
        return
    await callback_query.answer()
    if callback_query.message and callback_query.from_user:
        await list_admin_tasks(
            message_to_edit=callback_query.message,
            acting_user_id=callback_query.from_user.id,
            bot=bot,
            state=state,
            page=1
        )

@admin_panel_router.callback_query(F.data == "admin_panel:send_announcement")
async def admin_panel_send_announcement_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    from .admin_announce import ask_announcement_type
    if not callback_query.from_user or not await is_admin(callback_query.from_user.id, bot):
        await callback_query.answer("access denied.", show_alert=True)
        return
    await callback_query.answer()
    if callback_query.message:
        await ask_announcement_type(callback_query.message, state, bot)
