import asyncio

from aiogram import Router, Bot, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import Text, Bold
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.handlers.menu_utils import show_admin_panel
from telecopter.handlers.handler_states import AdminBroadcastStates
from telecopter.constants import (
    PROMPT_ADMIN_BROADCAST_TYPE,
    MSG_ADMIN_BROADCAST_CANCELLED,
    PROMPT_ADMIN_BROADCAST_TYPING_MESSAGE,
    MSG_ADMIN_BROADCAST_NO_USERS,
    MSG_ADMIN_BROADCAST_SENT_CONFIRM,
    MSG_ADMIN_BROADCAST_FAILURES_SUFFIX,
    BTN_BROADCAST_UNMUTED,
    BTN_BROADCAST_MUTED,
    BTN_BROADCAST_CANCEL,
    Icon,
    AdminBroadcastAction,
)


logger = setup_logger(__name__)

admin_broadcast_router = Router(name="admin_broadcast_router")

BROADCAST_TYPE_KEYBOARD = (
    InlineKeyboardBuilder()
    .add(
        InlineKeyboardButton(
            text=BTN_BROADCAST_UNMUTED, callback_data=f"broadcast_type:{AdminBroadcastAction.UNMUTED.value}"
        ),
        InlineKeyboardButton(text=BTN_BROADCAST_MUTED, callback_data=f"broadcast_type:{AdminBroadcastAction.MUTED.value}"),
        InlineKeyboardButton(
            text=BTN_BROADCAST_CANCEL, callback_data=f"broadcast_type:{AdminBroadcastAction.CANCEL.value}"
        ),
    )
    .adjust(2, 1)
    .as_markup()
)


async def ask_broadcast_type(message_event: Message, state: FSMContext, bot: Bot):
    await state.set_state(AdminBroadcastStates.choosing_type)
    text_obj = Text(PROMPT_ADMIN_BROADCAST_TYPE)
    try:
        if hasattr(message_event, "edit_text") and message_event.message_id:
            await message_event.edit_text(
                text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=BROADCAST_TYPE_KEYBOARD
            )
        elif message_event.chat:
            await bot.send_message(
                message_event.chat.id,
                text_obj.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=BROADCAST_TYPE_KEYBOARD,
            )
    except Exception as e:
        logger.error(f"error in ask_broadcast_type: {e}")
        if message_event.chat:
            await bot.send_message(
                message_event.chat.id,
                text_obj.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=BROADCAST_TYPE_KEYBOARD,
            )


@admin_broadcast_router.callback_query(
    StateFilter(AdminBroadcastStates.choosing_type), F.data.startswith("broadcast_type:")
)
async def process_broadcast_type_cb(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    action = callback_query.data.split(":")[1]
    await callback_query.answer()

    if action == AdminBroadcastAction.CANCEL.value:
        await state.clear()
        if callback_query.message:
            try:
                await callback_query.message.edit_text(
                    Text(MSG_ADMIN_BROADCAST_CANCELLED).as_markdown(), parse_mode="MarkdownV2", reply_markup=None
                )
            except Exception:
                logger.debug("could not edit message for broadcast cancel")
        await show_admin_panel(callback_query, bot)
        return

    is_muted = action == AdminBroadcastAction.MUTED.value
    await state.update_data(is_muted=is_muted)
    await state.set_state(AdminBroadcastStates.typing_message)

    muted_status = "muted" if is_muted else "unmuted"
    prompt_text_str = PROMPT_ADMIN_BROADCAST_TYPING_MESSAGE.format(muted_status=muted_status)
    prompt_text_obj = Text(prompt_text_str)
    if callback_query.message:
        try:
            await callback_query.message.edit_text(
                prompt_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None
            )
        except Exception as e:
            logger.debug(f"could not edit message for typing prompt: {e}")


@admin_broadcast_router.message(StateFilter(AdminBroadcastStates.typing_message), F.text)
async def process_broadcast_message_text(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        return

    data = await state.get_data()
    is_muted = data.get("is_muted", False)
    broadcast_text_from_admin = message.text
    await state.clear()

    formatted_broadcast_content = Text(
        Bold(Icon.BROADCASTMENT.value, " Broadcast from admin:"), "\n\n", Text(broadcast_text_from_admin)
    )
    final_message_to_send_md = formatted_broadcast_content.as_markdown()

    chat_ids = await db.get_all_user_chat_ids()
    admin_user_id = message.from_user.id

    if not chat_ids or (len(chat_ids) == 1 and admin_user_id in chat_ids and len(chat_ids) > 0):
        response_text_obj = Text(MSG_ADMIN_BROADCAST_NO_USERS)
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
            logger.error(f"failed to send broadcast to chat_id {cid}: {e}")
            failed_count += 1
        await asyncio.sleep(0.05)

    response_text_str = MSG_ADMIN_BROADCAST_SENT_CONFIRM.format(sent_count=sent_count)
    if failed_count > 0:
        response_text_str += MSG_ADMIN_BROADCAST_FAILURES_SUFFIX.format(failed_count=failed_count)
    response_text_obj = Text(response_text_str)
    await message.reply(response_text_obj.as_markdown(), parse_mode="MarkdownV2")

    await db.log_admin_action(
        admin_user_id=admin_user_id,
        action="broadcast_muted" if is_muted else "broadcast",
        details=f"Sent: {sent_count}, Failed: {failed_count}. Msg: {broadcast_text_from_admin[:100]}...",
    )
    await show_admin_panel(message, bot)
