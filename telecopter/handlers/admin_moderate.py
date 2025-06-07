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
from telecopter.handlers.common_utils import IsAdminFilter
from telecopter.handlers.handler_states import AdminInteractionStates
from telecopter.constants import (
    MSG_ERROR_UNEXPECTED,
    MSG_ADMIN_TASK_CLOSED_IN_VIEW,
    MSG_ADMIN_REQUEST_NOT_FOUND,
    MSG_ADMIN_CONTEXT_ERROR_FOR_NOTE,
    MSG_ADMIN_ACTION_WITH_NOTE_PROCESSED,
    MSG_ADMIN_MODERATE_UPDATE_FALLBACK,
    BTN_MOD_APPROVE,
    BTN_MOD_APPROVE_W_NOTE,
    BTN_MOD_DENY,
    BTN_MOD_DENY_W_NOTE,
    BTN_MOD_MARK_COMPLETED,
    BTN_MOD_MARK_RESOLVED,
    BTN_MOD_SHELVING_DECISION,
    BTN_MOD_ACKNOWLEDGE,
    PROMPT_ADMIN_NOTE_FOR_REQUEST,
    MSG_USER_REQUEST_APPROVED,
    MSG_USER_REQUEST_APPROVED_WITH_NOTE,
    MSG_USER_REQUEST_DENIED,
    MSG_USER_PROBLEM_RESOLVED,
    MSG_USER_PROBLEM_RESOLVED_WITH_NOTE,
    MSG_USER_REQUEST_COMPLETED,
    MSG_USER_REQUEST_COMPLETED_WITH_NOTE,
    MSG_USER_PROBLEM_ACKNOWLEDGED,
    MSG_ADMIN_ACTION_ERROR,
    MSG_ADMIN_ACTION_SUCCESS,
    MSG_ADMIN_ACTION_SUCCESS_WITH_NOTE,
    MSG_ADMIN_ACTION_NOTIFICATION_FAILED,
    MSG_ADMIN_ACTION_USER_NOT_FOUND,
    MSG_ADMIN_ACTION_DB_UPDATE_FAILED,
    MSG_ADMIN_ACTION_DB_UPDATE_FAILED_WITH_NOTE,
    MSG_ADMIN_ACTION_UNKNOWN_STATUS,
    MSG_ADMIN_ACTION_UNKNOWN,
    MSG_ADMIN_ACTION_TAKEN_BY,
    MSG_ADMIN_ACTION_TAKEN_SUFFIX,
    MSG_ADMIN_NOTE_LABEL,
    MSG_ITEM_MESSAGE_DIVIDER,
    AdminModerateAction,
    RequestStatus,
    RequestType,
)


logger = setup_logger(__name__)

admin_moderate_router = Router(name="admin_moderate_router")


def get_admin_request_action_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_MOD_APPROVE, callback_data=f"admin_act:{AdminModerateAction.APPROVE.value}:{request_id}")
    builder.button(
        text=BTN_MOD_APPROVE_W_NOTE,
        callback_data=f"admin_act:{AdminModerateAction.APPROVE_WITH_NOTE.value}:{request_id}",
    )
    builder.button(text=BTN_MOD_DENY, callback_data=f"admin_act:{AdminModerateAction.DENY.value}:{request_id}")
    builder.button(
        text=BTN_MOD_DENY_W_NOTE, callback_data=f"admin_act:{AdminModerateAction.DENY_WITH_NOTE.value}:{request_id}"
    )
    builder.button(
        text=BTN_MOD_MARK_COMPLETED,
        callback_data=f"admin_act:{AdminModerateAction.MARK_COMPLETED.value}_with_note:{request_id}",
    )
    builder.button(
        text=BTN_MOD_SHELVING_DECISION, callback_data=f"admin_act:{AdminModerateAction.CLOSE_TASK.value}:{request_id}"
    )
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def get_admin_report_action_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_MOD_ACKNOWLEDGE, callback_data=f"admin_act:{AdminModerateAction.ACKNOWLEDGE.value}:{request_id}"
    )
    builder.button(
        text=BTN_MOD_MARK_RESOLVED,
        callback_data=f"admin_act:{AdminModerateAction.MARK_RESOLVED.value}_with_note:{request_id}",
    )
    builder.button(
        text=BTN_MOD_SHELVING_DECISION, callback_data=f"admin_act:{AdminModerateAction.CLOSE_TASK.value}:{request_id}"
    )
    builder.adjust(1, 1, 1)
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

    if new_status == RequestStatus.APPROVED.value:
        if admin_note:
            user_notification_text_template = MSG_USER_REQUEST_APPROVED_WITH_NOTE
        else:
            user_notification_text_template = MSG_USER_REQUEST_APPROVED
    elif new_status == RequestStatus.DENIED.value:
        user_notification_text_template = MSG_USER_REQUEST_DENIED
    elif new_status == RequestStatus.COMPLETED.value:
        if original_request_type == RequestType.PROBLEM.value:
            if admin_note:
                user_notification_text_template = MSG_USER_PROBLEM_RESOLVED_WITH_NOTE
            else:
                user_notification_text_template = MSG_USER_PROBLEM_RESOLVED
        else:
            if admin_note:
                user_notification_text_template = MSG_USER_REQUEST_COMPLETED_WITH_NOTE
            else:
                user_notification_text_template = MSG_USER_REQUEST_COMPLETED
    elif new_status == RequestStatus.ACKNOWLEDGED.value:
        user_notification_text_template = MSG_USER_PROBLEM_ACKNOWLEDGED

    admin_confirm_message_core = MSG_ADMIN_ACTION_ERROR.format(request_id=request_id)

    if user_notification_text_template:
        db_update_successful = await db.update_request_status(request_id, new_status, admin_note=admin_note)
        if db_update_successful:
            if admin_note:
                admin_confirm_message_core = MSG_ADMIN_ACTION_SUCCESS_WITH_NOTE.format(
                    request_id=request_id, new_status=new_status
                )
            else:
                admin_confirm_message_core = MSG_ADMIN_ACTION_SUCCESS.format(
                    request_id=request_id, new_status=new_status
                )

            admin_confirm_message_core += ". User notified."

            await db.log_admin_action(
                acting_admin_user_id, action_key_for_log, request_id=request_id, details=admin_note
            )

            submitter_chat_id = await db.get_request_submitter_chat_id(request_id)
            if submitter_chat_id:
                user_msg_str = user_notification_text_template.format(title=original_request_title)
                user_msg_obj_parts = [Text(user_msg_str)]
                if admin_note:
                    user_msg_obj_parts.extend(["\n\n", Bold(MSG_ADMIN_NOTE_LABEL), " ", Italic(admin_note)])
                user_msg_obj = Text(*user_msg_obj_parts)
                try:
                    await bot.send_message(submitter_chat_id, text=user_msg_obj.as_markdown(), parse_mode="MarkdownV2")
                except Exception as e:
                    logger.error("failed to send status update to user for request %s: %s", request_id, e)
                    admin_confirm_message_core += MSG_ADMIN_ACTION_NOTIFICATION_FAILED
            else:
                admin_confirm_message_core += MSG_ADMIN_ACTION_USER_NOT_FOUND
        else:
            if admin_note:
                admin_confirm_message_core = MSG_ADMIN_ACTION_DB_UPDATE_FAILED_WITH_NOTE.format(
                    request_id=request_id, new_status=new_status
                )
            else:
                admin_confirm_message_core = MSG_ADMIN_ACTION_DB_UPDATE_FAILED.format(
                    request_id=request_id, new_status=new_status
                )
    else:
        admin_confirm_message_core = MSG_ADMIN_ACTION_UNKNOWN_STATUS.format(
            new_status=new_status, request_id=request_id
        )

    return admin_confirm_message_core


@admin_moderate_router.callback_query(F.data.startswith("admin_act:"), IsAdminFilter())
async def admin_action_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not (callback_query.message.text or callback_query.message.caption):
        logger.warning("admin_action_callback_handler: message text/caption is missing.")
        return

    action_full_key: str
    request_id: int
    try:
        parts = callback_query.data.split(":")
        action_full_key = parts[1]
        request_id = int(parts[2])
    except (IndexError, ValueError):
        logger.error("invalid admin action callback data: %s", callback_query.data)
        error_text_obj = Text(MSG_ERROR_UNEXPECTED)
        await callback_query.message.edit_text(error_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None)
        return

    if action_full_key == AdminModerateAction.CLOSE_TASK.value:
        try:
            text_obj = Text(MSG_ADMIN_TASK_CLOSED_IN_VIEW.format(request_id=request_id))
            await callback_query.message.edit_text(text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None)
        except Exception as e:
            logger.debug(f"failed to edit message for close_task: {e}")
        return

    original_request_row = await db.get_request_by_id(request_id)
    if not original_request_row:
        error_text_obj = Text(MSG_ADMIN_REQUEST_NOT_FOUND.format(request_id=request_id))
        await callback_query.message.edit_text(error_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None)
        return
    original_request = dict(original_request_row)
    original_message_content = callback_query.message.text or callback_query.message.caption

    base_action_key = action_full_key.replace("_with_note", "")

    if "_with_note" in action_full_key or base_action_key in [
        AdminModerateAction.MARK_COMPLETED.value,
        AdminModerateAction.MARK_RESOLVED.value,
    ]:
        await state.set_state(AdminInteractionStates.typing_admin_note)
        await state.update_data(
            admin_request_id=request_id,
            admin_base_action=base_action_key,
            original_admin_message_id=callback_query.message.message_id,
            original_admin_chat_id=callback_query.message.chat.id,
            original_message_text=original_message_content,
        )
        prompt_text_str = PROMPT_ADMIN_NOTE_FOR_REQUEST.format(request_id=request_id, base_action_key=base_action_key)
        prompt_text_obj = Text(prompt_text_str)
        await callback_query.message.edit_text(
            prompt_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None
        )
        return

    new_status: Optional[str] = None
    if base_action_key == AdminModerateAction.APPROVE.value:
        new_status = RequestStatus.APPROVED.value
    elif base_action_key == AdminModerateAction.DENY.value:
        new_status = RequestStatus.DENIED.value
    elif base_action_key == AdminModerateAction.MARK_COMPLETED.value:
        new_status = RequestStatus.COMPLETED.value
    elif base_action_key == AdminModerateAction.ACKNOWLEDGE.value:
        new_status = RequestStatus.ACKNOWLEDGED.value
    elif base_action_key == AdminModerateAction.MARK_RESOLVED.value:
        new_status = RequestStatus.COMPLETED.value

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
        admin_confirm_log_msg_raw = MSG_ADMIN_ACTION_UNKNOWN.format(
            action_full_key=action_full_key, request_id=request_id
        )

    updated_admin_notification_text_obj = Text(
        Text(original_message_content if original_message_content else "Request details"),
        MSG_ITEM_MESSAGE_DIVIDER,
        Bold(MSG_ADMIN_ACTION_TAKEN_BY),
        TextLink(callback_query.from_user.full_name, url=f"tg://user?id={callback_query.from_user.id}"),
        Text(MSG_ADMIN_ACTION_TAKEN_SUFFIX.format(action=action_full_key.replace("_", " "))),
        Text("\n"),
        Text(admin_confirm_log_msg_raw),
    )
    try:
        await callback_query.message.edit_text(
            updated_admin_notification_text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None
        )
    except Exception as e:
        logger.debug("failed to edit admin message: %s. sending new.", e)
        fallback_text_obj = Text(admin_confirm_log_msg_raw)
        await bot.send_message(callback_query.message.chat.id, fallback_text_obj.as_markdown(), parse_mode="MarkdownV2")


@admin_moderate_router.message(StateFilter(AdminInteractionStates.typing_admin_note), F.text, IsAdminFilter())
async def admin_note_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.text:
        return

    fsm_data = await state.get_data()
    request_id = fsm_data.get("admin_request_id")
    base_action = fsm_data.get("admin_base_action")
    original_admin_message_id = fsm_data.get("original_admin_message_id")
    original_admin_chat_id = fsm_data.get("original_admin_chat_id")
    original_message_text_from_fsm = fsm_data.get("original_message_text", f"Original request ID: {request_id}")

    admin_note_text_raw = truncate_text(message.text, MAX_NOTE_LENGTH)
    await state.clear()

    if not request_id or not base_action:
        error_text_obj = Text(MSG_ADMIN_CONTEXT_ERROR_FOR_NOTE)
        await message.answer(error_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    original_request_row = await db.get_request_by_id(request_id)
    if not original_request_row:
        error_text_obj = Text(MSG_ADMIN_REQUEST_NOT_FOUND.format(request_id=request_id))
        await message.answer(error_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return
    original_request = dict(original_request_row)

    new_status: Optional[str] = None
    if base_action == AdminModerateAction.APPROVE.value:
        new_status = RequestStatus.APPROVED.value
    elif base_action == AdminModerateAction.DENY.value:
        new_status = RequestStatus.DENIED.value
    elif base_action == AdminModerateAction.MARK_COMPLETED.value:
        new_status = RequestStatus.COMPLETED.value
    elif base_action == AdminModerateAction.MARK_RESOLVED.value:
        new_status = RequestStatus.COMPLETED.value

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
        admin_confirm_log_msg_raw = MSG_ADMIN_ACTION_UNKNOWN.format(action_full_key=base_action, request_id=request_id)

    reply_text_obj = Text(
        MSG_ADMIN_ACTION_WITH_NOTE_PROCESSED.format(request_id=request_id, log_message=admin_confirm_log_msg_raw)
    )
    await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")

    if original_admin_chat_id and original_admin_message_id:
        updated_admin_notification_text_obj = Text(
            Text(original_message_text_from_fsm),
            MSG_ITEM_MESSAGE_DIVIDER,
            Bold(MSG_ADMIN_ACTION_TAKEN_BY),
            TextLink(message.from_user.full_name, url=f"tg://user?id={message.from_user.id}"),
            Text(MSG_ADMIN_ACTION_TAKEN_SUFFIX.format(action=f"{base_action} with note")),
            Text("\n"),
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
                MSG_ADMIN_MODERATE_UPDATE_FALLBACK.format(
                    request_id=request_id, log_message=admin_confirm_log_msg_raw, admin_note=admin_note_text_raw
                )
            )
            await bot.send_message(original_admin_chat_id, fallback_text_obj.as_markdown(), parse_mode="MarkdownV2")
