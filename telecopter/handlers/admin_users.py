from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.handlers.common_utils import is_admin
from telecopter.constants import (
    USER_STATUS_APPROVED,
    USER_STATUS_REJECTED,
    CALLBACK_USER_APPROVAL_TASK_ACTION_PREFIX,
    CALLBACK_USER_APPROVAL_TASK_APPROVE,
    CALLBACK_USER_APPROVAL_TASK_REJECT,
    MSG_ACCESS_DENIED,
    MSG_ERROR_PROCESSING_ACTION_ALERT,
    MSG_ADMIN_TARGET_USER_NOT_FOUND_ALERT,
    MSG_ADMIN_UNKNOWN_ACTION_ALERT,
    MSG_USER_APPROVED_NOTIFICATION,
    MSG_USER_REJECTED_NOTIFICATION,
    MSG_ADMIN_USER_APPROVED_CONFIRM,
    MSG_ADMIN_USER_REJECTED_CONFIRM,
    MSG_ADMIN_USER_NOTIFY_FAIL_SUFFIX,
    REQUEST_STATUS_PENDING_ADMIN,
    REQUEST_STATUS_COMPLETED,
    MSG_TASK_ALREADY_PROCESSED_ALERT,
    MSG_TASK_ALREADY_PROCESSED_EDIT,
    MSG_USER_ALREADY_APPROVED_ALERT,
    MSG_USER_ALREADY_APPROVED_EDIT,
    MSG_USER_ALREADY_REJECTED_ALERT,
    MSG_USER_ALREADY_REJECTED_EDIT,
    MSG_ADMIN_REQUEST_NOT_FOUND,
)

logger = setup_logger(__name__)

admin_users_router = Router(name="admin_users_router")


@admin_users_router.callback_query(F.data.startswith(f"{CALLBACK_USER_APPROVAL_TASK_ACTION_PREFIX}:"))
async def handle_user_approval_action_from_task_cb(callback_query: CallbackQuery, bot: Bot):
    if (
        not callback_query.from_user
        or not await is_admin(callback_query.from_user.id, bot)
        or not callback_query.message
    ):
        await callback_query.answer(MSG_ACCESS_DENIED, show_alert=True)
        return

    try:
        _, action, target_user_id_str, task_request_id_str = callback_query.data.split(":")
        target_user_id = int(target_user_id_str)
        task_request_id = int(task_request_id_str)
    except ValueError:
        logger.error("invalid callback data for user approval task action: %s", callback_query.data)
        await callback_query.answer(MSG_ERROR_PROCESSING_ACTION_ALERT, show_alert=True)
        return

    original_task_info = await db.get_request_by_id(task_request_id)
    if not original_task_info:
        msg = MSG_ADMIN_REQUEST_NOT_FOUND.format(request_id=task_request_id)
        await callback_query.answer(msg, show_alert=True)
        try:
            await callback_query.message.edit_text(msg, reply_markup=None)
        except Exception as e:
            logger.debug("failed to edit message for non-existent task %s: %s", task_request_id, e)
        return

    current_task_status = original_task_info["status"]
    if current_task_status != REQUEST_STATUS_PENDING_ADMIN:
        final_message = MSG_TASK_ALREADY_PROCESSED_EDIT.format(task_id=task_request_id, status=current_task_status)
        await callback_query.answer(MSG_TASK_ALREADY_PROCESSED_ALERT, show_alert=True)
        try:
            await callback_query.message.edit_text(final_message, reply_markup=None)
        except Exception as e:
            logger.debug("failed to edit message for already processed task %s: %s", task_request_id, e)
        return

    target_user_db_info = await db.get_user(target_user_id)
    if not target_user_db_info:
        await callback_query.answer(MSG_ADMIN_TARGET_USER_NOT_FOUND_ALERT, show_alert=True)
        await db.update_request_status(
            task_request_id, "error_user_not_found", admin_note="Target user for approval task not found."
        )
        try:
            await callback_query.message.edit_text(
                f"Error: Target user ID {target_user_id} not found for task {task_request_id}\. Task closed due to"
                " error\.",
                reply_markup=None,
            )
        except Exception as e:
            logger.debug("failed to edit message for target user not found for task %s: %s", task_request_id, e)
        return

    target_user_name = str(target_user_id)
    try:
        if target_user_db_info["first_name"]:
            target_user_name = target_user_db_info["first_name"]
        elif target_user_db_info["username"]:
            target_user_name = target_user_db_info["username"]
    except KeyError:
        logger.warning(
            "first_name or username not found for user %s in db_info via key access, using id.", target_user_id
        )

    current_target_user_status = target_user_db_info["approval_status"]
    admin_user_id = callback_query.from_user.id
    action_result_text = ""
    new_user_status = ""
    new_task_status = REQUEST_STATUS_COMPLETED
    log_action_key = ""
    user_notification_message = ""

    if action == CALLBACK_USER_APPROVAL_TASK_APPROVE:
        if current_target_user_status == USER_STATUS_APPROVED:
            action_result_text = MSG_USER_ALREADY_APPROVED_EDIT.format(
                user_name=target_user_name, user_id=target_user_id, task_id=task_request_id
            )
            await callback_query.answer(MSG_USER_ALREADY_APPROVED_ALERT, show_alert=True)
            await db.update_request_status(
                task_request_id,
                new_task_status,
                admin_note=f"User was already approved. Task closed by admin {admin_user_id}.",
            )
            try:
                await callback_query.message.edit_text(action_result_text, reply_markup=None)
            except Exception as e:
                logger.debug("failed to edit message for user already approved task %s: %s", task_request_id, e)
            return
        new_user_status = USER_STATUS_APPROVED
        log_action_key = "user_approved_via_task"
        user_notification_message = MSG_USER_APPROVED_NOTIFICATION
        action_result_text = MSG_ADMIN_USER_APPROVED_CONFIRM.format(
            user_name=target_user_name, user_id=target_user_id, task_id=task_request_id
        )
    elif action == CALLBACK_USER_APPROVAL_TASK_REJECT:
        if current_target_user_status == USER_STATUS_REJECTED:
            action_result_text = MSG_USER_ALREADY_REJECTED_EDIT.format(
                user_name=target_user_name, user_id=target_user_id, task_id=task_request_id
            )
            await callback_query.answer(MSG_USER_ALREADY_REJECTED_ALERT, show_alert=True)
            await db.update_request_status(
                task_request_id,
                new_task_status,
                admin_note=f"User was already rejected. Task closed by admin {admin_user_id}.",
            )
            try:
                await callback_query.message.edit_text(action_result_text, reply_markup=None)
            except Exception as e:
                logger.debug("failed to edit message for user already rejected task %s: %s", task_request_id, e)
            return
        new_user_status = USER_STATUS_REJECTED
        log_action_key = "user_rejected_via_task"
        user_notification_message = MSG_USER_REJECTED_NOTIFICATION
        action_result_text = MSG_ADMIN_USER_REJECTED_CONFIRM.format(
            user_name=target_user_name, user_id=target_user_id, task_id=task_request_id
        )
    else:
        await callback_query.answer(MSG_ADMIN_UNKNOWN_ACTION_ALERT, show_alert=True)
        return

    await db.update_user_approval_status(target_user_id, new_user_status)
    await db.update_request_status(
        task_request_id, new_task_status, admin_note=f"Action taken by admin {admin_user_id}: {action}"
    )
    await db.log_admin_action(
        admin_user_id,
        log_action_key,
        details=f"target_user_id: {target_user_id}, new_status: {new_user_status}, task_id: {task_request_id}",
    )

    notification_sent_successfully = False
    chat_id_to_notify = None
    try:
        chat_id_to_notify = target_user_db_info["chat_id"]
    except KeyError:
        logger.error(
            "keyerror: 'chat_id' column unexpectedly missing for user %s from db.get_user result.", target_user_id
        )

    if chat_id_to_notify:
        try:
            await bot.send_message(chat_id_to_notify, user_notification_message)
            notification_sent_successfully = True
            logger.info(
                "successfully sent '%s' notification to user %s (chat_id: %s)",
                action,
                target_user_id,
                chat_id_to_notify,
            )
        except Exception as e:
            logger.error(
                "failed to notify user %s (chat_id: %s) about %s: %s", target_user_id, chat_id_to_notify, action, e
            )
    else:
        logger.warning(
            "chat_id for target user %s is invalid or missing (%s), cannot send notification.",
            target_user_id,
            chat_id_to_notify,
        )

    if not notification_sent_successfully:
        action_result_text += MSG_ADMIN_USER_NOTIFY_FAIL_SUFFIX

    if callback_query.message:
        try:
            await callback_query.message.edit_text(action_result_text, reply_markup=None)
        except Exception as e:
            logger.debug("failed to edit admin task message after user approval action: %s", e)
            await bot.send_message(callback_query.from_user.id, action_result_text)

    await callback_query.answer()
