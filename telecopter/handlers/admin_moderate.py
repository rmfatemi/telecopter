from typing import Optional

from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.formatting import Text, Bold, Italic, TextLink
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.utils import truncate_text
from telecopter.config import MAX_NOTE_LENGTH
from telecopter.handlers.common_utils import is_admin
from telecopter.handlers.handler_states import AdminInteractionStates


logger = setup_logger(__name__)

admin_moderate_router = Router(name="admin_moderate_router")


def get_admin_request_action_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ approve", callback_data=f"admin_act:approve:{request_id}")
    builder.button(text="📝 approve w/ note", callback_data=f"admin_act:approve_with_note:{request_id}")
    builder.button(text="❌ deny", callback_data=f"admin_act:deny:{request_id}")
    builder.button(text="📝 deny w/ note", callback_data=f"admin_act:deny_with_note:{request_id}")
    builder.button(text="🏁 mark completed", callback_data=f"admin_act:complete:{request_id}")
    builder.button(text="📝 complete w/ note", callback_data=f"admin_act:complete_with_note:{request_id}")
    builder.button(text="shelving_decision", callback_data=f"admin_act:close_task:{request_id}")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def get_admin_report_action_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👀 acknowledge", callback_data=f"admin_act:acknowledge:{request_id}")
    builder.button(text="🛠️ mark resolved", callback_data=f"admin_act:complete:{request_id}")
    builder.button(text="📝 resolve w/ note", callback_data=f"admin_act:complete_with_note:{request_id}")
    builder.button(text="shelving_decision", callback_data=f"admin_act:close_task:{request_id}")
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()


async def _perform_moderation_action_and_notify(
    bot: Bot,
    request_id: int,
    original_request_title: str,
    original_request_type: str,
    new_status: str,
    acting_admin_user_id: int,
    action_key_for_log: str,
    admin_note: Optional[str] = None,
) -> str:
    user_notification_text_template: Optional[str] = None

    if new_status == "approved":
        user_notification_text_template = 'great news! 🎉 your request for "{title}" has been approved.'
        if admin_note:
            user_notification_text_template = (
                'great news! 🎉 your request for "{title}" has been approved by the admin.'
            )
    elif new_status == "denied":
        user_notification_text_template = '📑 regarding your request for "{title}", the admin has denied it.'
    elif new_status == "completed":
        if original_request_type == "problem":
            user_notification_text_template = '🛠️ update: your problem report "{title}" has been marked as resolved.'
            if admin_note:
                user_notification_text_template = (
                    '🛠️ update: your problem report "{title}" has been marked as resolved by the admin.'
                )
        else:
            user_notification_text_template = '✅ update: your request for "{title}" is now completed and available!'
            if admin_note:
                user_notification_text_template = (
                    '✅ update: your request for "{title}" has been completed by the admin.'
                )
    elif new_status == "acknowledged":
        user_notification_text_template = '👀 update: your problem report "{title}" has been acknowledged by the admin.'

    admin_confirm_message_core = f"❗unexpected error processing request {request_id}"

    if user_notification_text_template:
        db_update_successful = await db.update_request_status(request_id, new_status, admin_note=admin_note)
        if db_update_successful:
            admin_confirm_message_core = f"request id {request_id} status set to {new_status}"
            if admin_note:
                admin_confirm_message_core += " with note"
            admin_confirm_message_core += ". user notified."

            await db.log_admin_action(
                acting_admin_user_id, action_key_for_log, request_id=request_id, details=admin_note
            )

            submitter_chat_id = await db.get_request_submitter_chat_id(request_id)
            if submitter_chat_id:
                user_msg_str = user_notification_text_template.format(title=original_request_title)
                user_msg_obj_parts = [Text(user_msg_str)]
                if admin_note:
                    user_msg_obj_parts.extend(["\n\n", Bold("admin's note:"), " ", Italic(admin_note)])
                user_msg_obj = Text(*user_msg_obj_parts)
                try:
                    await bot.send_message(submitter_chat_id, text=user_msg_obj.as_markdown(), parse_mode="MarkdownV2")
                except Exception as e:
                    logger.error("failed to send status update to user for request %s: %s", request_id, e)
                    admin_confirm_message_core += " (user notification failed)"
            else:
                admin_confirm_message_core += " (user chat_id not found)"
        else:
            admin_confirm_message_core = f"❗failed to update db status for request id {request_id} to {new_status}"
            if admin_note:
                admin_confirm_message_core += " with note"
    else:
        admin_confirm_message_core = (
            f"❗unknown new_status '{new_status}' or missing template for request id {request_id}"
        )

    return admin_confirm_message_core


@admin_moderate_router.callback_query(F.data.startswith("admin_act:"))
async def admin_action_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if (
        not callback_query.from_user
        or not callback_query.message
        or not (callback_query.message.text or callback_query.message.caption)
    ):
        logger.warning("admin_action_callback_handler: message text/caption is missing.")
        return

    if not await is_admin(callback_query.from_user.id, bot):
        if callback_query.message.chat:
            await bot.send_message(
                callback_query.message.chat.id,
                Text("⛔ this action is admin-only.").as_markdown(),
                parse_mode="MarkdownV2",
            )
        return

    action_full_key: str
    request_id: int
    try:
        parts = callback_query.data.split(":")
        action_full_key = parts[1]
        request_id = int(parts[2])
    except (IndexError, ValueError):
        logger.error("invalid admin action callback data: %s", callback_query.data)
        if callback_query.message:
            error_text_obj = Text("❗sorry, an unexpected error occurred. please try again later.")
            await callback_query.message.edit_text(
                error_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None
            )
        return

    if action_full_key == "close_task":
        try:
            if callback_query.message:
                text_obj = Text(f"task id {request_id} closed in this view.")
                await callback_query.message.edit_text(
                    text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None
                )
        except Exception as e:
            logger.debug(f"failed to edit message for close_task: {e}")
        return

    original_request_row = await db.get_request_by_id(request_id)
    if not original_request_row:
        if callback_query.message:
            error_text_obj = Text(f"❗error: request id {request_id} not found.")
            await callback_query.message.edit_text(
                error_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None
            )
        return
    original_request = dict(original_request_row)
    original_message_content = callback_query.message.text or callback_query.message.caption

    base_action_key = action_full_key.replace("_with_note", "")

    if "_with_note" in action_full_key:
        await state.set_state(AdminInteractionStates.typing_admin_note)
        await state.update_data(
            admin_request_id=request_id,
            admin_base_action=base_action_key,
            original_admin_message_id=callback_query.message.message_id,
            original_admin_chat_id=callback_query.message.chat.id,
            original_message_text=original_message_content,
        )
        prompt_text_str = (
            f"✍️ please send the note for request id {request_id} to be {base_action_key}d.\nyou can cancel from the"
            " admin panel if you return via /start."
        )
        prompt_text_obj = Text(prompt_text_str)
        if callback_query.message:
            await callback_query.message.edit_text(
                prompt_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None
            )
        return

    new_status: Optional[str] = None
    if base_action_key == "approve":
        new_status = "approved"
    elif base_action_key == "deny":
        new_status = "denied"
    elif base_action_key == "complete":
        new_status = "completed"
    elif base_action_key == "acknowledge":
        new_status = "acknowledged"

    admin_confirm_log_msg_raw: str
    if new_status:
        admin_confirm_log_msg_raw = await _perform_moderation_action_and_notify(
            bot=bot,
            request_id=request_id,
            original_request_title=original_request["title"],
            original_request_type=original_request["request_type"],
            new_status=new_status,
            acting_admin_user_id=callback_query.from_user.id,
            action_key_for_log=action_full_key,
            admin_note=None,
        )
    else:
        admin_confirm_log_msg_raw = f"❗unknown action '{action_full_key}' for request id {request_id}."

    if callback_query.message:
        updated_admin_notification_text_obj = Text(
            Text(original_message_content if original_message_content else "request details"),
            "\n\n---\n",
            Bold("action taken by "),
            TextLink(callback_query.from_user.full_name, url=f"tg://user?id={callback_query.from_user.id}"),
            Text(": "),
            Text(action_full_key.replace("_", " ")),
            Text("\n"),
            Text(admin_confirm_log_msg_raw),
        )
        try:
            await callback_query.message.edit_text(
                updated_admin_notification_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None
            )
        except Exception as e:
            logger.debug("failed to edit admin message: %s. sending new.", e)
            if callback_query.message.chat:
                fallback_text_obj = Text(admin_confirm_log_msg_raw)
                await bot.send_message(
                    callback_query.message.chat.id, fallback_text_obj.as_markdown(), parse_mode="MarkdownV2"
                )


@admin_moderate_router.message(StateFilter(AdminInteractionStates.typing_admin_note), F.text)
async def admin_note_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        return

    if not await is_admin(message.from_user.id, bot):
        reply_text_obj = Text("⛔ this action is admin-only.")
        await message.reply(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        await state.clear()
        return

    fsm_data = await state.get_data()
    request_id = fsm_data.get("admin_request_id")
    base_action = fsm_data.get("admin_base_action")
    original_admin_message_id = fsm_data.get("original_admin_message_id")
    original_admin_chat_id = fsm_data.get("original_admin_chat_id")
    original_message_text_from_fsm = fsm_data.get("original_message_text", f"original request id: {request_id}")

    admin_note_text_raw = truncate_text(message.text, MAX_NOTE_LENGTH)
    await state.clear()

    if not request_id or not base_action:
        error_text_obj = Text("❗error: could not retrieve context for adding note. please try the action again.")
        await message.answer(error_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    original_request_row = await db.get_request_by_id(request_id)
    if not original_request_row:
        error_text_obj = Text(f"❗error: request id {request_id} not found.")
        await message.answer(error_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return
    original_request = dict(original_request_row)

    new_status: Optional[str] = None
    if base_action == "approve":
        new_status = "approved"
    elif base_action == "deny":
        new_status = "denied"
    elif base_action == "complete":
        new_status = "completed"

    admin_confirm_log_msg_raw: str
    full_action_key = f"{base_action}_with_note"
    if new_status:
        admin_confirm_log_msg_raw = await _perform_moderation_action_and_notify(
            bot=bot,
            request_id=request_id,
            original_request_title=original_request["title"],
            original_request_type=original_request["request_type"],
            new_status=new_status,
            acting_admin_user_id=message.from_user.id,
            action_key_for_log=full_action_key,
            admin_note=admin_note_text_raw,
        )
    else:
        admin_confirm_log_msg_raw = (
            f"❗error processing admin action '{base_action}' with note for request id {request_id}."
        )

    reply_text_obj = Text(f"✅ action (with note) for request id {request_id} processed: {admin_confirm_log_msg_raw}")
    await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")

    if original_admin_chat_id and original_admin_message_id:
        updated_admin_notification_text_obj = Text(
            Text(original_message_text_from_fsm),
            "\n\n---\n",
            Bold("action taken by "),
            TextLink(message.from_user.full_name, url=f"tg://user?id={message.from_user.id}"),
            Text(f": {base_action} with note\n"),
            Italic(admin_note_text_raw),
            Text("\n"),
            Text(admin_confirm_log_msg_raw.split(".")[0] + "."),
        )
        try:
            await bot.edit_message_text(
                chat_id=original_admin_chat_id,
                message_id=original_admin_message_id,
                text=updated_admin_notification_text_obj.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=None,
            )
        except Exception as e:
            logger.debug("failed to update original admin message after note: %s", e)
            fallback_text_obj = Text(
                f"update for request id {request_id}: {admin_confirm_log_msg_raw} (note: {admin_note_text_raw})"
            )
            await bot.send_message(original_admin_chat_id, fallback_text_obj.as_markdown(), parse_mode="MarkdownV2")
