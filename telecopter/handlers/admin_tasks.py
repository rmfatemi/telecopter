from typing import List, Union, Optional

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.formatting import Text, Bold, Italic, Code, as_list, TextLink
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import DEFAULT_PAGE_SIZE
from telecopter.utils import truncate_text, format_request_for_admin
from telecopter.handlers.common_utils import is_admin, format_user_for_admin_notification
from telecopter.handlers.admin_moderate import get_admin_request_action_keyboard, get_admin_report_action_keyboard
from telecopter.constants import (
    REQUEST_TYPE_USER_APPROVAL,
    TITLE_ADMIN_TASKS_LIST,
    MSG_NO_ADMIN_TASKS_PAGE_1,
    MSG_NO_ADMIN_TASKS_OTHER_PAGE,
    BTN_PREVIOUS_TASKS,
    BTN_NEXT_TASKS,
    BTN_BACK_TO_ADMIN_PANEL,
    BTN_REVIEW_USER_APPROVAL_TASK,
    CALLBACK_ADMIN_TASKS_PAGE_PREFIX,
    CALLBACK_ADMIN_TASKS_BACK_PANEL,
    CALLBACK_ADMIN_TASK_MODERATE_PREFIX,
    CALLBACK_ADMIN_REVIEW_USER_APPROVAL_PREFIX,
    MSG_ACCESS_DENIED,
    MSG_ERROR_PROCESSING_ACTION_ALERT,
    MSG_ADMIN_REQUEST_NOT_FOUND,
    MSG_ADMIN_TASK_IDENTIFY_ERROR,
    MSG_ADMIN_TASK_USER_NOT_FOUND_ERROR,
    MSG_NO_TASKS_INFO_TO_DISPLAY,
    BTN_APPROVE_USER_ACTION,
    BTN_REJECT_USER_ACTION,
    CALLBACK_USER_APPROVAL_TASK_ACTION_PREFIX,
    CALLBACK_USER_APPROVAL_TASK_APPROVE,
    CALLBACK_USER_APPROVAL_TASK_REJECT,
    MSG_ADMIN_USER_APPROVAL_TASK_DETAILS_TITLE,
    MSG_ADMIN_USER_APPROVAL_TASK_USER_INFO_LABEL,
    MSG_ERROR_UNEXPECTED,
)

logger = setup_logger(__name__)

admin_tasks_router = Router(name="admin_tasks_router")


def get_admin_tasks_pagination_keyboard(page: int, total_pages: int) -> Optional[InlineKeyboardMarkup]:
    builder = InlineKeyboardBuilder()

    prev_button: Optional[InlineKeyboardButton] = None
    if page > 1:
        prev_button = InlineKeyboardButton(
            text=BTN_PREVIOUS_TASKS, callback_data=f"{CALLBACK_ADMIN_TASKS_PAGE_PREFIX}:{page - 1}"
        )

    next_button: Optional[InlineKeyboardButton] = None
    if page < total_pages:
        next_button = InlineKeyboardButton(
            text=BTN_NEXT_TASKS, callback_data=f"{CALLBACK_ADMIN_TASKS_PAGE_PREFIX}:{page + 1}"
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
    if not await is_admin(acting_user_id, bot):
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

    content_elements: List[Union[Text, Bold, Italic, Code, TextLink]] = []
    tasks_keyboard_builder = InlineKeyboardBuilder()

    if not requests_rows and page == 1:
        content_elements.append(Text(MSG_NO_ADMIN_TASKS_PAGE_1))
    elif not requests_rows and page > 1:
        content_elements.append(Text(MSG_NO_ADMIN_TASKS_OTHER_PAGE.format(page=page)))
    else:
        content_elements.append(Bold(TITLE_ADMIN_TASKS_LIST.format(page=page, total_pages=total_pages)))
        content_elements.append(Text("\n"))

        for req_row in requests_rows:
            req = dict(req_row)
            req_id = req["request_id"]
            req_type = req["request_type"]
            req_title = req["title"]
            req_status = req["status"]
            task_user_id = req["user_id"]
            created_date = req["created_at"][:10]

            item_text_parts = []

            if req_type == REQUEST_TYPE_USER_APPROVAL:
                item_text_parts.append(Text(f"👤 User Approval: {truncate_text(req_title, 40)} \(Task ID: {req_id}\)"))
                item_text_parts.append(Text(f"\n   Status: {req_status}, For User ID: {task_user_id}"))
                tasks_keyboard_builder.button(
                    text=BTN_REVIEW_USER_APPROVAL_TASK,
                    callback_data=f"{CALLBACK_ADMIN_REVIEW_USER_APPROVAL_PREFIX}:{req_id}:{task_user_id}",
                )
            else:
                media_problem_icon = "🎬" if req_type in ["movie", "tv", "manual_media"] else "⚠️"
                submitter_info_row = await db.get_user(task_user_id)
                submitter_name_disp = str(task_user_id)
                if submitter_info_row:
                    submitter_info = dict(submitter_info_row)
                    submitter_name_disp = submitter_info.get("first_name") or str(task_user_id)

                item_text_parts.append(
                    Text(f"{media_problem_icon} ID:{req_id} \- {truncate_text(req_title, 35)} ({req_status})")
                )
                item_text_parts.append(Text(f"\n   By: {submitter_name_disp}, On: {created_date}"))
                tasks_keyboard_builder.button(
                    text=f"Mod ID:{req_id}", callback_data=f"{CALLBACK_ADMIN_TASK_MODERATE_PREFIX}:{req_id}"
                )

            content_elements.append(as_list(*item_text_parts, sep=""))
            content_elements.append(Text("\-\-\-"))

        tasks_keyboard_builder.adjust(1)

    pagination_kb_markup = get_admin_tasks_pagination_keyboard(page, total_pages)
    if pagination_kb_markup:
        for row_of_buttons in pagination_kb_markup.inline_keyboard:
            tasks_keyboard_builder.row(*row_of_buttons)

    tasks_keyboard_builder.row(
        InlineKeyboardButton(text=BTN_BACK_TO_ADMIN_PANEL, callback_data=CALLBACK_ADMIN_TASKS_BACK_PANEL)
    )

    final_text_content_obj = (
        as_list(*content_elements, sep="\n") if content_elements else Text(MSG_NO_TASKS_INFO_TO_DISPLAY)
    )
    reply_markup_to_send = tasks_keyboard_builder.as_markup()

    try:
        await message_to_edit.edit_text(
            final_text_content_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=reply_markup_to_send
        )
    except Exception as e:
        logger.error(f"failed to edit admin tasks message: {e}, sending new.")
        if message_to_edit.chat:
            await bot.send_message(
                message_to_edit.chat.id,
                final_text_content_obj.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=reply_markup_to_send,
            )


@admin_tasks_router.callback_query(F.data.startswith(CALLBACK_ADMIN_TASKS_PAGE_PREFIX + ":"))
async def admin_tasks_page_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    if (
        not callback_query.from_user
        or not await is_admin(callback_query.from_user.id, bot)
        or not callback_query.message
    ):
        text_obj = Text(MSG_ERROR_PROCESSING_ACTION_ALERT)
        await callback_query.answer(text_obj.as_markdown(), show_alert=True)
        return

    acting_user_id = callback_query.from_user.id
    page = 1
    try:
        page = int(callback_query.data.split(":")[1])
    except (IndexError, ValueError):
        logger.warning(f"invalid page number in admin_tasks_page_cb: {callback_query.data}")

    await callback_query.answer()
    await list_admin_tasks(
        message_to_edit=callback_query.message, acting_user_id=acting_user_id, bot=bot, state=state, page=page
    )


@admin_tasks_router.callback_query(F.data == CALLBACK_ADMIN_TASKS_BACK_PANEL)
async def admin_tasks_back_panel_cb(callback_query: CallbackQuery, bot: Bot):
    from .admin_panel import show_admin_panel

    if not callback_query.from_user or not await is_admin(callback_query.from_user.id, bot):
        text_obj = Text(MSG_ACCESS_DENIED)
        await callback_query.answer(text_obj.as_markdown(), show_alert=True)
        return
    await callback_query.answer()
    await show_admin_panel(callback_query, bot)


@admin_tasks_router.callback_query(
    F.data.startswith(CALLBACK_ADMIN_TASK_MODERATE_PREFIX + ":")
    | F.data.startswith(CALLBACK_ADMIN_REVIEW_USER_APPROVAL_PREFIX + ":")
)
async def admin_task_review_or_moderate_trigger_cb(callback_query: CallbackQuery, bot: Bot):
    if (
        not callback_query.from_user
        or not await is_admin(callback_query.from_user.id, bot)
        or not callback_query.message
    ):
        text_obj = Text(MSG_ACCESS_DENIED)
        await callback_query.answer(text_obj.as_markdown(), show_alert=True)
        return

    action_parts = callback_query.data.split(":")
    action_prefix = action_parts[0]
    request_id_str = action_parts[1]

    try:
        request_id = int(request_id_str)
    except ValueError:
        logger.error(f"invalid request_id in {action_prefix} callback: {request_id_str}")
        text_obj = Text(MSG_ADMIN_TASK_IDENTIFY_ERROR)
        await callback_query.message.answer(text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    db_request_row = await db.get_request_by_id(request_id)
    if not db_request_row:
        text_obj = Text(MSG_ADMIN_REQUEST_NOT_FOUND.format(request_id=request_id))
        await callback_query.message.answer(text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    db_request_dict = dict(db_request_row)
    request_type = db_request_dict["request_type"]
    task_related_user_id = db_request_dict["user_id"]

    target_chat_id_for_action_panel = callback_query.from_user.id
    await callback_query.answer()

    if action_prefix == CALLBACK_ADMIN_REVIEW_USER_APPROVAL_PREFIX and request_type == REQUEST_TYPE_USER_APPROVAL:
        target_user_for_approval_id = task_related_user_id
        target_user_details_text = await format_user_for_admin_notification(target_user_for_approval_id, bot)

        approval_task_info = Text(
            Bold(MSG_ADMIN_USER_APPROVAL_TASK_DETAILS_TITLE.format(task_id=request_id)),
            "\n\n",
            MSG_ADMIN_USER_APPROVAL_TASK_USER_INFO_LABEL,
            target_user_details_text,
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.button(
            text=BTN_APPROVE_USER_ACTION,
            callback_data=f"{CALLBACK_USER_APPROVAL_TASK_ACTION_PREFIX}:{CALLBACK_USER_APPROVAL_TASK_APPROVE}:{target_user_for_approval_id}:{request_id}",
        )
        keyboard.button(
            text=BTN_REJECT_USER_ACTION,
            callback_data=f"{CALLBACK_USER_APPROVAL_TASK_ACTION_PREFIX}:{CALLBACK_USER_APPROVAL_TASK_REJECT}:{target_user_for_approval_id}:{request_id}",
        )
        keyboard.adjust(1)
        await bot.send_message(
            chat_id=target_chat_id_for_action_panel,
            text=approval_task_info.as_markdown(),
            parse_mode="MarkdownV2",
            reply_markup=keyboard.as_markup(),
        )
    elif action_prefix == CALLBACK_ADMIN_TASK_MODERATE_PREFIX and request_type != REQUEST_TYPE_USER_APPROVAL:
        submitter_user_info_row = await db.get_user(task_related_user_id)
        if not submitter_user_info_row:
            text_obj = Text(MSG_ADMIN_TASK_USER_NOT_FOUND_ERROR.format(request_id=request_id))
            await bot.send_message(target_chat_id_for_action_panel, text_obj.as_markdown(), parse_mode="MarkdownV2")
            return

        admin_msg_obj = format_request_for_admin(db_request_dict, dict(submitter_user_info_row))
        admin_keyboard = None
        if request_type == "problem":
            admin_keyboard = get_admin_report_action_keyboard(request_id)
        else:
            admin_keyboard = get_admin_request_action_keyboard(request_id)

        await bot.send_message(
            chat_id=target_chat_id_for_action_panel,
            text=admin_msg_obj.as_markdown(),
            parse_mode="MarkdownV2",
            reply_markup=admin_keyboard,
        )
    else:
        logger.warning(
            "mismatched action prefix (%s) and request type (%s) for task %s", action_prefix, request_type, request_id
        )
        text_obj = Text(MSG_ERROR_UNEXPECTED)
        await bot.send_message(target_chat_id_for_action_panel, text_obj.as_markdown(), parse_mode="MarkdownV2")
