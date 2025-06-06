from typing import List, Union

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.formatting import Text, Bold, Italic, Code, as_list, TextLink
from aiogram.utils.keyboard import InlineKeyboardBuilder

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import DEFAULT_PAGE_SIZE
from telecopter.handlers.common_utils import IsAdminFilter
from telecopter.handlers.menu_utils import show_admin_panel
from telecopter.constants import (
    USER_STATUS_APPROVED,
    USER_STATUS_REJECTED,
    USER_STATUS_PENDING_APPROVAL,
    CALLBACK_MANAGE_USERS_PREFIX,
    CALLBACK_MANAGE_USERS_APPROVE,
    CALLBACK_MANAGE_USERS_REJECT,
    CALLBACK_MANAGE_USERS_PAGE_PREFIX,
    CALLBACK_ADMIN_TASKS_BACK_PANEL,
    MSG_ACCESS_DENIED,
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
    TITLE_MANAGE_USERS_LIST,
    MSG_NO_PENDING_USERS_PAGE_1,
    MSG_NO_MORE_PENDING_USERS,
    BTN_PREVIOUS_PAGE,
    BTN_NEXT_PAGE,
    BTN_BACK_TO_ADMIN_PANEL,
    BTN_APPROVE_USER,
    BTN_REJECT_USER,
    ICON_USER_APPROVAL,
    MSG_ITEM_MESSAGE_DIVIDER,
)


logger = setup_logger(__name__)

admin_users_router = Router(name="admin_users_router")


def get_user_management_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if page > 1:
        builder.button(text=BTN_PREVIOUS_PAGE, callback_data=f"{CALLBACK_MANAGE_USERS_PAGE_PREFIX}:{page - 1}")
    if page < total_pages:
        builder.button(text=BTN_NEXT_PAGE, callback_data=f"{CALLBACK_MANAGE_USERS_PAGE_PREFIX}:{page + 1}")

    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=BTN_BACK_TO_ADMIN_PANEL, callback_data=CALLBACK_ADMIN_TASKS_BACK_PANEL))
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
                Text(ICON_USER_APPROVAL, " ", Bold(TextLink(display_name, url=f"tg://user?id={user_id}"))),
                Text("   Requested on: ", Italic(created_date)),
                sep="\n",
            )
            content_elements.append(user_text)

            keyboard_builder.row(
                InlineKeyboardButton(
                    text=BTN_APPROVE_USER,
                    callback_data=f"{CALLBACK_MANAGE_USERS_PREFIX}:{CALLBACK_MANAGE_USERS_APPROVE}:{user_id}",
                ),
                InlineKeyboardButton(
                    text=BTN_REJECT_USER,
                    callback_data=f"{CALLBACK_MANAGE_USERS_PREFIX}:{CALLBACK_MANAGE_USERS_REJECT}:{user_id}",
                ),
            )
            content_elements.append(Text(MSG_ITEM_MESSAGE_DIVIDER))

    if content_elements and isinstance(content_elements[-1], Text) and content_elements[-1].render()[0] == MSG_ITEM_MESSAGE_DIVIDER:
        content_elements.pop()

    pagination_markup = get_user_management_pagination_keyboard(page, total_pages)
    for row in pagination_markup.inline_keyboard:
        keyboard_builder.row(*row)

    final_text_content_obj = as_list(*content_elements, sep="\n")
    await message_to_edit.edit_text(
        final_text_content_obj.as_markdown(),
        parse_mode="MarkdownV2",
        reply_markup=keyboard_builder.as_markup(),
    )


@admin_users_router.callback_query(F.data.startswith(f"{CALLBACK_MANAGE_USERS_PAGE_PREFIX}:"), IsAdminFilter())
async def pending_users_page_cb(callback_query: CallbackQuery, bot: Bot):
    try:
        page = int(callback_query.data.split(":")[1])
    except (IndexError, ValueError):
        await callback_query.answer(MSG_ERROR_PROCESSING_ACTION_ALERT, show_alert=True)
        return

    await callback_query.answer()
    await list_pending_users(message_to_edit=callback_query.message, bot=bot, page=page)


@admin_users_router.callback_query(F.data.startswith(f"{CALLBACK_MANAGE_USERS_PREFIX}:"), IsAdminFilter())
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
        await list_pending_users(message_to_edit=callback_query.message, bot=bot, page=1)
        return

    target_user = dict(target_user_row)

    if target_user["approval_status"] != USER_STATUS_PENDING_APPROVAL:
        alert_text = (
            MSG_USER_ALREADY_APPROVED_ALERT
            if target_user["approval_status"] == USER_STATUS_APPROVED
            else MSG_USER_ALREADY_REJECTED_ALERT
        )
        await callback_query.answer(alert_text, show_alert=True)
        await list_pending_users(message_to_edit=callback_query.message, bot=bot, page=1)
        return

    new_status, log_action, user_notification, admin_confirm_msg = "", "", "", ""
    user_name = target_user.get("first_name") or str(target_user_id)

    if action == CALLBACK_MANAGE_USERS_APPROVE:
        new_status = USER_STATUS_APPROVED
        log_action = "user_approved"
        user_notification = MSG_USER_APPROVED_NOTIFICATION
        admin_confirm_msg = MSG_ADMIN_USER_APPROVED_CONFIRM.format(user_name=user_name, user_id=target_user_id)
    elif action == CALLBACK_MANAGE_USERS_REJECT:
        new_status = USER_STATUS_REJECTED
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
        await bot.send_message(
            target_user["chat_id"],
            notification_text_obj.as_markdown(),
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        logger.error(f"Failed to notify user {target_user_id} about approval status change: {e}")
        admin_confirm_msg += MSG_ADMIN_USER_NOTIFY_FAIL_SUFFIX

    await callback_query.answer(admin_confirm_msg, show_alert=True)
    await list_pending_users(message_to_edit=callback_query.message, bot=bot, page=1)


@admin_users_router.callback_query(F.data == CALLBACK_ADMIN_TASKS_BACK_PANEL, IsAdminFilter())
async def admin_users_back_panel_cb(callback_query: CallbackQuery, bot: Bot):
    await callback_query.answer()
    await show_admin_panel(callback_query, bot)
