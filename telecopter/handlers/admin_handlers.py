import asyncio
from typing import List, Union, Optional

from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.formatting import Text, Bold, Italic, Code, as_list, TextLink
from aiogram.utils.keyboard import InlineKeyboardBuilder

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import DEFAULT_PAGE_SIZE, MAX_NOTE_LENGTH
from telecopter.utils import format_request_for_admin, format_request_item_display_parts, truncate_text
from telecopter.handlers.menu_utils import show_admin_panel
from telecopter.handlers.common_utils import is_admin, IsAdminFilter
from telecopter.handlers.handler_states import AdminInteractionStates, AdminBroadcastStates
from telecopter.constants import (
    AdminPanelCallback,
    AdminTasksCallback,
    UserManageCallback,
    UserStatus,
    RequestStatus,
    RequestType,
    AdminModerateAction,
    AdminBroadcastAction,
    Icon,
    TITLE_ADMIN_TASKS_LIST,
    MSG_NO_ADMIN_TASKS_PAGE_1,
    MSG_NO_ADMIN_TASKS_OTHER_PAGE,
    BTN_PREVIOUS_PAGE,
    BTN_NEXT_PAGE,
    BTN_BACK_TO_ADMIN_PANEL,
    MSG_ACCESS_DENIED,
    MSG_ADMIN_REQUEST_NOT_FOUND,
    MSG_ADMIN_TASK_IDENTIFY_ERROR,
    MSG_ADMIN_TASK_USER_NOT_FOUND_ERROR,
    MSG_NO_TASKS_INFO_TO_DISPLAY,
    MSG_ITEM_MESSAGE_DIVIDER,
    TITLE_MANAGE_USERS_LIST,
    MSG_NO_PENDING_USERS_PAGE_1,
    MSG_NO_MORE_PENDING_USERS,
    BTN_APPROVE_USER,
    BTN_REJECT_USER,
    MSG_ERROR_PROCESSING_ACTION_ALERT,
    MSG_ADMIN_TARGET_USER_NOT_FOUND_ALERT,
    MSG_ADMIN_UNKNOWN_ACTION_ALERT,
    MSG_USER_APPROVED_NOTIFICATION,
    MSG_USER_REJECTED_NOTIFICATION,
    MSG_ADMIN_USER_APPROVED_CONFIRM,
    MSG_ADMIN_USER_REJECTED_CONFIRM,
    MSG_ADMIN_USER_NOTIFY_FAIL_SUFFIX,
    MSG_USER_ALREADY_APPROVED_ALERT,
    MSG_USER_ALREADY_REJECTED_ALERT,
    PROMPT_ADMIN_BROADCAST_TYPE,
    MSG_ADMIN_BROADCAST_CANCELLED,
    PROMPT_ADMIN_BROADCAST_TYPING_MESSAGE,
    MSG_ADMIN_BROADCAST_NO_USERS,
    MSG_ADMIN_BROADCAST_SENT_CONFIRM,
    MSG_ADMIN_BROADCAST_FAILURES_SUFFIX,
    BTN_BROADCAST_UNMUTED,
    BTN_BROADCAST_MUTED,
    BTN_BROADCAST_CANCEL,
    MSG_ERROR_UNEXPECTED,
    MSG_ADMIN_TASK_CLOSED_IN_VIEW,
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
)


logger = setup_logger(__name__)

admin_router = Router(name="admin_router")


# --- Admin Panel Logic ---

@admin_router.callback_query(F.data == f"{AdminPanelCallback.PREFIX.value}:{AdminPanelCallback.VIEW_TASKS.value}", IsAdminFilter())
async def admin_panel_view_tasks_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    await callback_query.answer()
    if callback_query.message and callback_query.from_user:
        await list_admin_tasks(
            message_to_edit=callback_query.message,
            acting_user_id=callback_query.from_user.id,
            bot=bot,
            state=state,
            page=1,
        )

@admin_router.callback_query(F.data == f"{AdminPanelCallback.PREFIX.value}:{AdminPanelCallback.MANAGE_USERS.value}", IsAdminFilter())
async def admin_panel_manage_users_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    await callback_query.answer()
    if callback_query.message:
        await list_pending_users(message_to_edit=callback_query.message, bot=bot, page=1)

@admin_router.callback_query(
    F.data == f"{AdminPanelCallback.PREFIX.value}:{AdminPanelCallback.SEND_BROADCASTMENT.value}", IsAdminFilter()
)
async def admin_panel_send_broadcast_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    await callback_query.answer()
    if callback_query.message:
        await ask_broadcast_type(callback_query.message, state, bot)


# --- Admin Tasks Logic ---

def get_admin_tasks_pagination_keyboard(page: int, total_pages: int) -> Optional[InlineKeyboardMarkup]:
    builder = InlineKeyboardBuilder()
    prev_button: Optional[InlineKeyboardButton] = None
    if page > 1:
        prev_button = InlineKeyboardButton(
            text=BTN_PREVIOUS_PAGE, callback_data=f"{AdminTasksCallback.PAGE_PREFIX.value}:{page - 1}"
        )

    next_button: Optional[InlineKeyboardButton] = None
    if page < total_pages:
        next_button = InlineKeyboardButton(
            text=BTN_NEXT_PAGE, callback_data=f"{AdminTasksCallback.PAGE_PREFIX.value}:{page + 1}"
        )

    if prev_button and next_button:
        builder.row(prev_button, next_button)
    elif prev_button:
        builder.row(prev_button)
    elif next_button:
        builder.row(next_button)
    else:
        return None

    return builder.as_markup()

async def list_admin_tasks(message_to_edit: Message, acting_user_id: int, bot: Bot, state: FSMContext, page: int = 1):
    if not await is_admin(acting_user_id):
        logger.warning("list_admin_tasks called by non-admin user %s.", acting_user_id)
        if message_to_edit.chat:
            text_obj = Text(MSG_ACCESS_DENIED)
            await bot.send_message(message_to_edit.chat.id, text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    await state.clear()

    requests_rows = await db.get_actionable_admin_requests(page, DEFAULT_PAGE_SIZE)
    total_requests = await db.get_actionable_admin_requests_count()
    total_pages = (total_requests + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
    total_pages = max(1, total_pages)

    content_elements: List[Union[Text, Bold, Italic, Code]] = []
    tasks_keyboard_builder = InlineKeyboardBuilder()

    if not requests_rows and page == 1:
        content_elements.append(Text(MSG_NO_ADMIN_TASKS_PAGE_1))
    elif not requests_rows and page > 1:
        content_elements.append(Text(MSG_NO_ADMIN_TASKS_OTHER_PAGE.format(page=page)))
    else:
        content_elements.append(Bold(TITLE_ADMIN_TASKS_LIST.format(page=page, total_pages=total_pages)))
        if requests_rows:
            content_elements.append(Text("\n"))

        for req_row in requests_rows:
            req = dict(req_row)
            req_id = req["request_id"]
            task_user_id = req["user_id"]

            submitter_name_disp = str(task_user_id)
            submitter_info_row = await db.get_user(task_user_id)
            if submitter_info_row:
                submitter_info = dict(submitter_info_row)
                name_options = [submitter_info.get("first_name"), submitter_info.get("username")]
                chosen_name = next((name for name in name_options if name and name.strip()), None)
                submitter_name_disp = chosen_name or str(task_user_id)

            item_text_parts = format_request_item_display_parts(
                req, view_context="admin_list_item", submitter_name_override=submitter_name_disp
            )

            tasks_keyboard_builder.button(
                text=f"Review Task ({req_id})", callback_data=f"{AdminTasksCallback.MODERATE_PREFIX.value}:{req_id}"
            )

            if item_text_parts:
                content_elements.append(as_list(*item_text_parts, sep=""))
                content_elements.append(Text(MSG_ITEM_MESSAGE_DIVIDER))

    if tasks_keyboard_builder.buttons:
        tasks_keyboard_builder.adjust(1)

    pagination_kb_markup = get_admin_tasks_pagination_keyboard(page, total_pages)
    if pagination_kb_markup:
        for row_of_buttons in pagination_kb_markup.inline_keyboard:
            tasks_keyboard_builder.row(*row_of_buttons)

    tasks_keyboard_builder.row(
        InlineKeyboardButton(text=BTN_BACK_TO_ADMIN_PANEL, callback_data=AdminTasksCallback.BACK_TO_PANEL.value)
    )

    if (
        content_elements
        and isinstance(content_elements[-1], Text)
        and content_elements[-1].render()[0] == MSG_ITEM_MESSAGE_DIVIDER
    ):
        content_elements.pop()

    final_text_content_obj = (
        as_list(*content_elements, sep="\n") if content_elements else Text(MSG_NO_TASKS_INFO_TO_DISPLAY)
    )
    reply_markup_to_send = tasks_keyboard_builder.as_markup()

    try:
        await message_to_edit.edit_text(
            final_text_content_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=reply_markup_to_send
        )
    except Exception as e:
        logger.error(f"failed to edit admin tasks message: {e}, sending new if possible.")
        if message_to_edit.chat:
            await bot.send_message(
                message_to_edit.chat.id,
                final_text_content_obj.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=reply_markup_to_send,
            )

@admin_router.callback_query(F.data.startswith(AdminTasksCallback.PAGE_PREFIX.value + ":"), IsAdminFilter())
async def admin_tasks_page_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    acting_user_id = callback_query.from_user.id
    page = 1
    try:
        page_str = callback_query.data.split(":")[1]
        page = int(page_str)
    except (IndexError, ValueError):
        logger.warning(f"invalid page number in admin_tasks_page_cb: {callback_query.data}")
        await callback_query.answer("error: invalid page reference.", show_alert=True)
        return

    await callback_query.answer()
    if callback_query.message:
        await list_admin_tasks(
            message_to_edit=callback_query.message, acting_user_id=acting_user_id, bot=bot, state=state, page=page
        )

@admin_router.callback_query(F.data == AdminTasksCallback.BACK_TO_PANEL.value, IsAdminFilter())
async def admin_tasks_back_panel_cb(callback_query: CallbackQuery, bot: Bot):
    await callback_query.answer()
    if callback_query.message:
        await show_admin_panel(callback_query, bot)


@admin_router.callback_query(F.data.startswith(AdminTasksCallback.MODERATE_PREFIX.value + ":"), IsAdminFilter())
async def admin_task_moderate_trigger_cb(callback_query: CallbackQuery, bot: Bot):
    action_parts = callback_query.data.split(":")
    if len(action_parts) < 2:
        logger.error(f"invalid callback data format: {callback_query.data}")
        await callback_query.answer(MSG_ADMIN_TASK_IDENTIFY_ERROR, show_alert=True)
        return

    try:
        request_id = int(action_parts[1])
    except ValueError:
        logger.error(f"invalid request_id in moderate callback: {action_parts[1]}")
        if callback_query.message:
            await callback_query.message.reply(Text(MSG_ADMIN_TASK_IDENTIFY_ERROR).as_markdown(), parse_mode="MarkdownV2")
        await callback_query.answer()
        return

    db_request_row = await db.get_request_by_id(request_id)
    if not db_request_row:
        if callback_query.message:
            text_obj = Text(MSG_ADMIN_REQUEST_NOT_FOUND.format(request_id=request_id))
            await callback_query.message.reply(text_obj.as_markdown(), parse_mode="MarkdownV2")
        await callback_query.answer()
        return

    db_request_dict = dict(db_request_row)
    task_related_user_id = db_request_dict["user_id"]
    submitter_user_info_row = await db.get_user(task_related_user_id)
    if not submitter_user_info_row:
        text_obj = Text(MSG_ADMIN_TASK_USER_NOT_FOUND_ERROR.format(request_id=request_id))
        await bot.send_message(callback_query.from_user.id, text_obj.as_markdown(), parse_mode="MarkdownV2")
        await callback_query.answer()
        return

    await callback_query.answer()
    admin_msg_obj = format_request_for_admin(db_request_dict, dict(submitter_user_info_row))
    admin_keyboard = None
    if db_request_dict["request_type"] == RequestType.PROBLEM.value:
        admin_keyboard = get_admin_report_action_keyboard(request_id)
    else:
        admin_keyboard = get_admin_request_action_keyboard(request_id)
    await bot.send_message(
        chat_id=callback_query.from_user.id,
        text=admin_msg_obj.as_markdown(),
        parse_mode="MarkdownV2",
        reply_markup=admin_keyboard,
    )


# --- Admin Users Logic ---

def get_user_management_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if page > 1:
        builder.button(text=BTN_PREVIOUS_PAGE, callback_data=f"{UserManageCallback.PAGE_PREFIX.value}:{page - 1}")
    if page < total_pages:
        builder.button(text=BTN_NEXT_PAGE, callback_data=f"{UserManageCallback.PAGE_PREFIX.value}:{page + 1}")

    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text=BTN_BACK_TO_ADMIN_PANEL, callback_data=AdminTasksCallback.BACK_TO_PANEL.value)
    )
    return builder.as_markup()

async def list_pending_users(message_to_edit: Message, bot: Bot, page: int = 1):
    pending_users = await db.get_pending_approval_users(page, DEFAULT_PAGE_SIZE)
    total_users = await db.get_pending_approval_users_count()
    total_pages = (total_users + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
    total_pages = max(1, total_pages)

    content_elements: List[Union[Text, Bold, Italic, Code, TextLink]] = []
    keyboard_builder = InlineKeyboardBuilder()

    if not pending_users and page == 1:
        content_elements.append(Text(MSG_NO_PENDING_USERS_PAGE_1))
    elif not pending_users:
        content_elements.append(Text(MSG_NO_MORE_PENDING_USERS.format(page=page)))
    else:
        content_elements.append(Bold(TITLE_MANAGE_USERS_LIST.format(page=page, total_pages=total_pages)))
        content_elements.append(Text("\n"))

        for user_row in pending_users:
            user = dict(user_row)
            user_id = user["user_id"]
            first_name = user.get("first_name", f"User ID: {user_id}")
            username = user.get("username")
            created_date = user.get("created_at", "Unknown")[:10]

            display_name = f"@{username}" if username else first_name

            user_text = as_list(
                Text(Icon.USER_APPROVAL.value, " ", Bold(TextLink(display_name, url=f"tg://user?id={user_id}"))),
                Text("   Requested on: ", Italic(created_date)),
                sep="\n",
            )
            content_elements.append(user_text)

            keyboard_builder.row(
                InlineKeyboardButton(
                    text=BTN_APPROVE_USER,
                    callback_data=f"{UserManageCallback.PREFIX.value}:{UserManageCallback.APPROVE.value}:{user_id}",
                ),
                InlineKeyboardButton(
                    text=BTN_REJECT_USER,
                    callback_data=f"{UserManageCallback.PREFIX.value}:{UserManageCallback.REJECT.value}:{user_id}",
                ),
            )
            content_elements.append(Text(MSG_ITEM_MESSAGE_DIVIDER))

    if (
        content_elements
        and isinstance(content_elements[-1], Text)
        and content_elements[-1].render()[0] == MSG_ITEM_MESSAGE_DIVIDER
    ):
        content_elements.pop()

    pagination_markup = get_user_management_pagination_keyboard(page, total_pages)
    for row in pagination_markup.inline_keyboard:
        keyboard_builder.row(*row)

    final_text_content_obj = as_list(*content_elements, sep="\n")
    if message_to_edit:
        await message_to_edit.edit_text(
            final_text_content_obj.as_markdown(),
            parse_mode="MarkdownV2",
            reply_markup=keyboard_builder.as_markup(),
        )

@admin_router.callback_query(F.data.startswith(f"{UserManageCallback.PAGE_PREFIX.value}:"), IsAdminFilter())
async def pending_users_page_cb(callback_query: CallbackQuery, bot: Bot):
    try:
        page = int(callback_query.data.split(":")[1])
    except (IndexError, ValueError):
        await callback_query.answer(MSG_ERROR_PROCESSING_ACTION_ALERT, show_alert=True)
        return

    await callback_query.answer()
    if callback_query.message:
        await list_pending_users(message_to_edit=callback_query.message, bot=bot, page=page)

@admin_router.callback_query(F.data.startswith(f"{UserManageCallback.PREFIX.value}:"), IsAdminFilter())
async def handle_user_approval_action(callback_query: CallbackQuery, bot: Bot):
    try:
        _, action, target_user_id_str = callback_query.data.split(":")
        target_user_id = int(target_user_id_str)
    except (ValueError, IndexError):
        await callback_query.answer(MSG_ERROR_PROCESSING_ACTION_ALERT, show_alert=True)
        return

    target_user_row = await db.get_user(target_user_id)
    if not target_user_row:
        await callback_query.answer(MSG_ADMIN_TARGET_USER_NOT_FOUND_ALERT, show_alert=True)
        if callback_query.message:
            await list_pending_users(message_to_edit=callback_query.message, bot=bot, page=1)
        return

    target_user = dict(target_user_row)

    if target_user["approval_status"] != UserStatus.PENDING_APPROVAL.value:
        alert_text = (
            MSG_USER_ALREADY_APPROVED_ALERT
            if target_user["approval_status"] == UserStatus.APPROVED.value
            else MSG_USER_ALREADY_REJECTED_ALERT
        )
        await callback_query.answer(alert_text, show_alert=True)
        if callback_query.message:
            await list_pending_users(message_to_edit=callback_query.message, bot=bot, page=1)
        return

    new_status, log_action, user_notification, admin_confirm_msg = "", "", "", ""
    user_name = target_user.get("first_name") or str(target_user_id)

    if action == UserManageCallback.APPROVE.value:
        new_status = UserStatus.APPROVED.value
        log_action = "user_approved"
        user_notification = MSG_USER_APPROVED_NOTIFICATION
        admin_confirm_msg = MSG_ADMIN_USER_APPROVED_CONFIRM.format(user_name=user_name, user_id=target_user_id)
    elif action == UserManageCallback.REJECT.value:
        new_status = UserStatus.REJECTED.value
        log_action = "user_rejected"
        user_notification = MSG_USER_REJECTED_NOTIFICATION
        admin_confirm_msg = MSG_ADMIN_USER_REJECTED_CONFIRM.format(user_name=user_name, user_id=target_user_id)
    else:
        await callback_query.answer(MSG_ADMIN_UNKNOWN_ACTION_ALERT, show_alert=True)
        return

    await db.update_user_approval_status(target_user_id, new_status)
    await db.log_admin_action(
        admin_user_id=callback_query.from_user.id,
        action=log_action,
        details=f"Target User ID: {target_user_id}",
    )

    try:
        notification_text_obj = Text(user_notification)
        await bot.send_message(target_user["chat_id"], notification_text_obj.as_markdown(), parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"failed to notify user {target_user_id} about approval status change: {e}")
        admin_confirm_msg += MSG_ADMIN_USER_NOTIFY_FAIL_SUFFIX

    await callback_query.answer(admin_confirm_msg, show_alert=True)
    if callback_query.message:
        await list_pending_users(message_to_edit=callback_query.message, bot=bot, page=1)


# --- Admin Moderate Logic ---

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
        callback_data=f"admin_act:{AdminModerateAction.MARK_COMPLETED.value}:{request_id}",
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
        callback_data=f"admin_act:{AdminModerateAction.MARK_RESOLVED.value}:{request_id}",
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
        user_notification_text_template = (
            MSG_USER_REQUEST_APPROVED_WITH_NOTE if admin_note else MSG_USER_REQUEST_APPROVED
        )
    elif new_status == RequestStatus.DENIED.value:
        user_notification_text_template = MSG_USER_REQUEST_DENIED
    elif new_status == RequestStatus.COMPLETED.value:
        if original_request_type == RequestType.PROBLEM.value:
            user_notification_text_template = (
                MSG_USER_PROBLEM_RESOLVED_WITH_NOTE if admin_note else MSG_USER_PROBLEM_RESOLVED
            )
        else:
            user_notification_text_template = (
                MSG_USER_REQUEST_COMPLETED_WITH_NOTE if admin_note else MSG_USER_REQUEST_COMPLETED
            )
    elif new_status == RequestStatus.ACKNOWLEDGED.value:
        user_notification_text_template = MSG_USER_PROBLEM_ACKNOWLEDGED

    admin_confirm_message_core = MSG_ADMIN_ACTION_ERROR.format(request_id=request_id)

    if user_notification_text_template:
        db_update_successful = await db.update_request_status(request_id, new_status, admin_note=admin_note)
        if db_update_successful:
            admin_confirm_message_core = (
                MSG_ADMIN_ACTION_SUCCESS_WITH_NOTE.format(request_id=request_id, new_status=new_status)
                if admin_note
                else MSG_ADMIN_ACTION_SUCCESS.format(request_id=request_id, new_status=new_status)
            )

            await db.log_admin_action(
                acting_admin_user_id, action_key_for_log, request_id=request_id, details=admin_note
            )

            submitter_chat_id = await db.get_request_submitter_chat_id(request_id)
            if submitter_chat_id:
                user_msg_str = user_notification_text_template.format(title=original_request_title)
                user_msg_obj_parts = [Text(user_msg_str)]
                if admin_note:
                    user_msg_obj_parts.extend([Text("\n\n"), Bold(MSG_ADMIN_NOTE_LABEL), Text(" "), Italic(admin_note)])
                user_msg_obj = Text(*user_msg_obj_parts)
                try:
                    await bot.send_message(submitter_chat_id, text=user_msg_obj.as_markdown(), parse_mode="MarkdownV2")
                    admin_confirm_message_core += ". User notified."
                except Exception as e:
                    logger.error("failed to send status update to user for request %s: %s", request_id, e)
                    admin_confirm_message_core += MSG_ADMIN_ACTION_NOTIFICATION_FAILED
            else:
                admin_confirm_message_core += MSG_ADMIN_ACTION_USER_NOT_FOUND
        else:
            admin_confirm_message_core = (
                MSG_ADMIN_ACTION_DB_UPDATE_FAILED_WITH_NOTE.format(request_id=request_id, new_status=new_status)
                if admin_note
                else MSG_ADMIN_ACTION_DB_UPDATE_FAILED.format(request_id=request_id, new_status=new_status)
            )
    else:
        admin_confirm_message_core = MSG_ADMIN_ACTION_UNKNOWN_STATUS.format(
            new_status=new_status, request_id=request_id
        )

    return admin_confirm_message_core

@admin_router.callback_query(F.data.startswith("admin_act:"), IsAdminFilter())
async def admin_action_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.message or not (callback_query.message.text or callback_query.message.caption):
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

    if "_with_note" in action_full_key:
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

    if original_message_content:
        updated_admin_notification_text_obj = Text(
            Text(original_message_content),
            Text("\n"),
            Text(MSG_ITEM_MESSAGE_DIVIDER),
            Text("\n"),
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
            if callback_query.message.chat:
                await bot.send_message(callback_query.message.chat.id, fallback_text_obj.as_markdown(), parse_mode="MarkdownV2")

@admin_router.message(StateFilter(AdminInteractionStates.typing_admin_note), F.text, IsAdminFilter())
async def admin_note_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.text or not message.from_user:
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
            Text("\n"),
            Text(MSG_ITEM_MESSAGE_DIVIDER),
            Text("\n"),
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


# --- Admin Broadcast Logic ---

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
        if isinstance(message_event, Message) and message_event.chat:
             await bot.send_message(
                message_event.chat.id,
                text_obj.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=BROADCAST_TYPE_KEYBOARD,
            )
        elif isinstance(message_event, CallbackQuery) and message_event.message:
             await message_event.message.edit_text(
                text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=BROADCAST_TYPE_KEYBOARD
            )
    except Exception as e:
        logger.error(f"error in ask_broadcast_type: {e}")
        if hasattr(message_event, "chat") and message_event.chat:
            await bot.send_message(
                message_event.chat.id,
                text_obj.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=BROADCAST_TYPE_KEYBOARD,
            )


@admin_router.callback_query(
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
        if callback_query.message:
             await show_admin_panel(callback_query.message, bot)
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

@admin_router.message(StateFilter(AdminBroadcastStates.typing_message), F.text, IsAdminFilter())
async def process_broadcast_message_text(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        return

    data = await state.get_data()
    is_muted = data.get("is_muted", False)
    broadcast_text_from_admin = message.text
    await state.clear()

    formatted_broadcast_content = Text(
        Bold(Icon.BROADCASTMENT.value, " Broadcast from admin:"), Text("\n\n"), Text(broadcast_text_from_admin)
    )
    final_message_to_send_md = formatted_broadcast_content.as_markdown()

    chat_ids = await db.get_all_user_chat_ids()
    admin_user_id = message.from_user.id

    if not chat_ids or (len(chat_ids) == 1 and admin_user_id in chat_ids):
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
