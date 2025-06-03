import asyncio

from aiogram import Router, Bot, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import Text, Bold
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.handlers.handler_states import AdminAnnounceStates


logger = setup_logger(__name__)

admin_announce_router = Router(name="admin_announce_router")


ANNOUNCE_TYPE_KEYBOARD = (
    InlineKeyboardBuilder()
    .add(
        InlineKeyboardButton(text="🔊 unmuted", callback_data="announce_type:unmuted"),
        InlineKeyboardButton(text="🤫 muted", callback_data="announce_type:muted"),
        InlineKeyboardButton(text="❌ cancel", callback_data="announce_type:cancel_to_panel"),
    )
    .adjust(2, 1)
    .as_markup()
)

async def ask_announcement_type(message_event: Message, state: FSMContext, bot: Bot):
    await state.set_state(AdminAnnounceStates.choosing_type)
    text_obj = Text("📢 choose announcement type:")
    try:
        if hasattr(message_event, 'edit_text') and message_event.message_id:
            await message_event.edit_text(text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=ANNOUNCE_TYPE_KEYBOARD)
        elif message_event.chat:
             await bot.send_message(message_event.chat.id, text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=ANNOUNCE_TYPE_KEYBOARD)
    except Exception as e:
        logger.error(f"error in ask_announcement_type: {e}")
        if message_event.chat:
             await bot.send_message(message_event.chat.id, text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=ANNOUNCE_TYPE_KEYBOARD)


@admin_announce_router.callback_query(StateFilter(AdminAnnounceStates.choosing_type), F.data.startswith("announce_type:"))
async def process_announcement_type_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    action = callback_query.data.split(":")[1]
    await callback_query.answer()

    if action == "cancel_to_panel":
        from .admin_panel import show_admin_panel
        await state.clear()
        if callback_query.message:
            try:
                await callback_query.message.edit_text(Text("announcement cancelled.").as_markdown(), parse_mode="MarkdownV2")
            except Exception:
                logger.debug("could not edit message for announcement cancel")
        await show_admin_panel(callback_query, bot)
        return

    is_muted = action == "muted"
    await state.update_data(is_muted=is_muted)
    await state.set_state(AdminAnnounceStates.typing_message)

    prompt_text_str = f"✍️ please type your {'muted' if is_muted else 'unmuted'} announcement message below.\nyou can cancel from the admin panel if you return via /start."
    prompt_text_obj = Text(prompt_text_str)
    if callback_query.message:
        await callback_query.message.edit_text(prompt_text_obj.as_markdown(), parse_mode="MarkdownV2")

@admin_announce_router.message(StateFilter(AdminAnnounceStates.typing_message), F.text)
async def process_announcement_message_text(message: Message, state: FSMContext, bot: Bot):
    from .admin_panel import show_admin_panel

    if not message.from_user or not message.text:
        return

    data = await state.get_data()
    is_muted = data.get("is_muted", False)
    announcement_text_from_admin = message.text
    await state.clear()

    formatted_announcement_content = Text(
        Bold("📢 announcement from admin:"), "\n\n", Text(announcement_text_from_admin)
    )
    final_message_to_send_md = formatted_announcement_content.as_markdown()

    chat_ids = await db.get_all_user_chat_ids()
    admin_user_id = message.from_user.id
    if not chat_ids:
        response_text_obj = Text("👥 no registered users found to send announcement to.")
        await message.reply(response_text_obj.as_markdown(), parse_mode="MarkdownV2")
        await show_admin_panel(message, bot)
        return

    sent_count = 0
    failed_count = 0
    for cid in chat_ids:
        if cid == admin_user_id:
            continue
        try:
            await bot.send_message(
                chat_id=cid, text=final_message_to_send_md, parse_mode="MarkdownV2", disable_notification=is_muted
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"failed to send announcement to chat_id {cid}: {e}")
            failed_count += 1
        await asyncio.sleep(0.05)

    response_text_str = f"✅ announcement sent to {sent_count} users."
    if failed_count > 0:
        response_text_str += f" {failed_count} failures."
    response_text_obj = Text(response_text_str)
    await message.reply(response_text_obj.as_markdown(), parse_mode="MarkdownV2")

    await db.log_admin_action(
        admin_user_id=admin_user_id,
        action="announce_muted" if is_muted else "announce",
        details=f"sent: {sent_count}, failed: {failed_count}. msg: {announcement_text_from_admin[:100]}",
    )
    await show_admin_panel(message, bot)
