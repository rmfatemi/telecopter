import asyncio

from typing import Optional

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.utils.formatting import Text, Bold, Italic, TextLink
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.utils import truncate_text
from telecopter.config import MAX_NOTE_LENGTH

from telecopter.handlers.common import _is_admin

logger = setup_logger(__name__)

admin_router = Router(name="admin_router")


class AdminInteractionStates(StatesGroup):
    typing_admin_note = State()


def get_admin_request_action_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve", callback_data=f"admin_act:approve:{request_id}")
    builder.button(text="📝 Approve w/ Note", callback_data=f"admin_act:approve_with_note:{request_id}")
    builder.button(text="❌ Deny", callback_data=f"admin_act:deny:{request_id}")
    builder.button(text="📝 Deny w/ Note", callback_data=f"admin_act:deny_with_note:{request_id}")
    builder.button(text="🏁 Mark Completed", callback_data=f"admin_act:complete:{request_id}")
    builder.button(text="📝 Complete w/ Note", callback_data=f"admin_act:complete_with_note:{request_id}")
    builder.adjust(2)
    return builder.as_markup()


def get_admin_report_action_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👀 Acknowledge", callback_data=f"admin_act:acknowledge:{request_id}")
    builder.button(text="🛠️ Mark Resolved", callback_data=f"admin_act:complete:{request_id}")
    builder.button(text="📝 Resolve w/ Note", callback_data=f"admin_act:complete_with_note:{request_id}")
    builder.adjust(1)
    return builder.as_markup()


@admin_router.message(Command("announce", "announce_muted"))
async def announce_command_handler(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        return

    if not await _is_admin(message.from_user.id, bot):
        await message.reply("⛔ This command is admin-only.")
        return

    if not command.args:
        await message.reply(f"✍️ Please provide a message. Usage: `/{command.command} <message>`")
        return

    announcement_text_from_admin = command.args
    is_muted = command.command == "announce_muted"

    formatted_announcement_content = Text(
        Bold("📢 Announcement from Admin:"), "\n\n", Text(announcement_text_from_admin)
    )
    final_message_to_send_md = formatted_announcement_content.as_markdown()

    chat_ids = await db.get_all_user_chat_ids()
    if not chat_ids:
        await message.reply("👥 No registered users found to send announcement to.")
        return

    sent_count = 0
    failed_count = 0
    for cid in chat_ids:
        if cid == message.from_user.id:
            continue
        try:
            await bot.send_message(
                chat_id=cid, text=final_message_to_send_md, parse_mode="MarkdownV2", disable_notification=is_muted
            )
            sent_count += 1
        except Exception as e:
            logger.error("failed to send announcement to chat_id %s: %s", cid, e)
            failed_count += 1
        await asyncio.sleep(0.05)

    response_text = f"✅ Announcement sent to {sent_count} users."
    if failed_count > 0:
        response_text += f" {failed_count} failures."
    await message.reply(response_text)

    await db.log_admin_action(
        admin_user_id=message.from_user.id,
        action="announce_muted" if is_muted else "announce",
        details=f"Sent: {sent_count}, Failed: {failed_count}. Msg: {announcement_text_from_admin[:100]}",
    )


@admin_router.callback_query(F.data.startswith("admin_act:"))
async def admin_action_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message or not callback_query.message.text:
        return

    if not await _is_admin(callback_query.from_user.id, bot):
        await callback_query.message.answer("⛔ This action is admin-only.")
        return

    try:
        parts = callback_query.data.split(":")
        action_full_key = parts[1]
        request_id = int(parts[2])
    except (IndexError, ValueError):
        logger.error("invalid admin action callback data: %s", callback_query.data)
        await callback_query.message.edit_text(
            "❗Sorry, an unexpected error occurred. Please try again later.", reply_markup=None
        )
        return

    original_request_row = await db.get_request_by_id(request_id)
    if not original_request_row:
        await callback_query.message.edit_text(f"❗Error: Request ID {request_id} not found.", reply_markup=None)
        return
    original_request = dict(original_request_row)

    base_action_key = action_full_key.replace("_with_note", "")

    if "_with_note" in action_full_key:
        await state.set_state(AdminInteractionStates.typing_admin_note)
        await state.update_data(
            {
                "admin_request_id": request_id,
                "admin_base_action": base_action_key,
                "original_admin_message_id": callback_query.message.message_id,
                "original_admin_chat_id": callback_query.message.chat.id,
            }
        )
        await callback_query.message.edit_text(
            f"✍️ Please send the note for Request ID {request_id} to be {base_action_key}d. Or /cancel.",
            reply_markup=None,
        )
        return

    new_status: Optional[str] = None
    user_notification_text_template: Optional[str] = None
    admin_note_to_save: Optional[str] = None

    if base_action_key == "approve":
        new_status = "approved"
        user_notification_text_template = 'Great news! 🎉 Your request for "{title}" has been approved.'
    elif base_action_key == "deny":
        new_status = "denied"
        user_notification_text_template = '📑 Regarding your request for "{title}", the admin has denied it.'
    elif base_action_key == "complete":
        new_status = "completed"
        if original_request["request_type"] == "problem":
            user_notification_text_template = '🛠️ Update: Your problem report "{title}" has been marked as resolved.'
        else:
            user_notification_text_template = '✅ Update: Your request for "{title}" is now completed and available!'
    elif base_action_key == "acknowledge":
        new_status = "acknowledged"
        user_notification_text_template = '👀 Update: Your problem report "{title}" has been acknowledged by the admin.'

    admin_confirm_log_msg = f"❗unexpected error processing request {request_id}."
    if new_status and user_notification_text_template:
        success = await db.update_request_status(request_id, new_status, admin_note=admin_note_to_save)
        if success:
            admin_confirm_log_msg = f"Request ID {request_id} status set to {new_status}. User notified."
            await db.log_admin_action(callback_query.from_user.id, action_full_key, request_id=request_id)

            submitter_chat_id = await db.get_request_submitter_chat_id(request_id)
            if submitter_chat_id:
                user_msg_obj = Text(user_notification_text_template.format(title=original_request["title"]))
                try:
                    await bot.send_message(submitter_chat_id, text=user_msg_obj.as_markdown(), parse_mode="MarkdownV2")
                except Exception as e:
                    logger.error("failed to send status update to user for request %s: %s", request_id, e)
        else:
            admin_confirm_log_msg = f"❗Failed to update status for Request ID {request_id} to {new_status}."
    else:
        admin_confirm_log_msg = f"❗Unknown action '{action_full_key}' for request id {request_id}."

    updated_admin_notification_text_obj = Text(
        Text(callback_query.message.text),
        "\n\n---\n",
        Bold("Action taken by "),
        TextLink(callback_query.from_user.full_name, url=f"tg://user?id={callback_query.from_user.id}"),
        Text(":"),
        Text(f"\n{admin_confirm_log_msg}"),
    )
    try:
        await callback_query.message.edit_text(
            updated_admin_notification_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None
        )
    except Exception as e:
        logger.debug("failed to edit admin message: %s. sending new.", e)
        await bot.send_message(callback_query.message.chat.id, admin_confirm_log_msg)


@admin_router.message(StateFilter(AdminInteractionStates.typing_admin_note), F.text)
async def admin_note_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        return

    if not await _is_admin(message.from_user.id, bot):
        await message.reply("⛔ This action is admin-only.")
        return

    fsm_data = await state.get_data()
    request_id = fsm_data.get("admin_request_id")
    base_action = fsm_data.get("admin_base_action")
    original_admin_message_id = fsm_data.get("original_admin_message_id")
    original_admin_chat_id = fsm_data.get("original_admin_chat_id")

    admin_note_text = truncate_text(message.text, MAX_NOTE_LENGTH)

    await state.clear()

    if not request_id or not base_action:
        await message.answer("❗Error: Could not retrieve context for adding note. Please try the action again.")
        return

    original_request_row = await db.get_request_by_id(request_id)
    if not original_request_row:
        await message.answer(f"❗Error: Request ID {request_id} not found.")
        return
    original_request = dict(original_request_row)

    new_status: Optional[str] = None
    user_notification_text_template: Optional[str] = None

    if base_action == "approve":
        new_status = "approved"
        user_notification_text_template = 'Great news! 🎉 Your request for "{title}" has been approved by the admin.'
    elif base_action == "deny":
        new_status = "denied"
        user_notification_text_template = '📑 Regarding your request for "{title}", the admin has denied it.'
    elif base_action == "complete":
        new_status = "completed"
        if original_request["request_type"] == "problem":
            user_notification_text_template = (
                '🛠️ Update: Your problem report "{title}" has been marked as resolved by the admin.'
            )
        else:
            user_notification_text_template = '✅ Update: Your request for "{title}" has been completed by the admin.'

    admin_confirm_log_msg = f"❗unexpected error processing request {request_id} with note."
    if new_status and user_notification_text_template:
        success = await db.update_request_status(request_id, new_status, admin_note=admin_note_text)
        if success:
            full_action_key = f"{base_action}_with_note"
            admin_confirm_log_msg = f"Request ID {request_id} has been {base_action}d with note. User notified."
            await db.log_admin_action(
                message.from_user.id, full_action_key, request_id=request_id, details=admin_note_text
            )

            submitter_chat_id = await db.get_request_submitter_chat_id(request_id)
            if submitter_chat_id:
                user_msg_obj = Text(
                    Text(user_notification_text_template.format(title=original_request["title"])),
                    "\n\n",
                    Bold("Admin's note:"),
                    " ",
                    Italic(admin_note_text),
                )
                try:
                    await bot.send_message(submitter_chat_id, text=user_msg_obj.as_markdown(), parse_mode="MarkdownV2")
                except Exception as e:
                    logger.error("failed to send status update with admin note to user for req %s: %s", request_id, e)
        else:
            admin_confirm_log_msg = f"❗Failed to update Request ID {request_id} with your note."
    else:
        admin_confirm_log_msg = (
            f"❗Error processing admin action '{base_action}' with note for Request ID {request_id}."
        )

    await message.answer(f"✅ Action (with note) for Request ID {request_id} processed: {admin_confirm_log_msg}")

    if original_admin_chat_id and original_admin_message_id:
        try:
            original_admin_message = await bot.edit_message_text(
                chat_id=original_admin_chat_id,
                message_id=original_admin_message_id,
                text=(
                    f"Original request (ID: {request_id}) - Action taken with note by"
                    f" {message.from_user.full_name}.\n{admin_confirm_log_msg}"
                ),
                reply_markup=None,
            )
        except Exception as e:
            logger.debug("failed to update original admin message after note: %s", e)
