from typing import List, Union, Optional

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.formatting import Text, Bold, Italic, Code, as_list
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import DEFAULT_PAGE_SIZE
from telecopter.utils import format_request_for_admin, format_request_item_display_parts
from telecopter.handlers.common_utils import is_admin, IsAdminFilter
from telecopter.handlers.menu_utils import show_admin_panel
from telecopter.handlers.admin_moderate import get_admin_request_action_keyboard, get_admin_report_action_keyboard
from telecopter.constants import (
    TITLE_ADMIN_TASKS_LIST,
    MSG_NO_ADMIN_TASKS_PAGE_1,
    MSG_NO_ADMIN_TASKS_OTHER_PAGE,
    BTN_PREVIOUS_PAGE,
    BTN_NEXT_PAGE,
    BTN_BACK_TO_ADMIN_PANEL,
    CALLBACK_ADMIN_TASKS_PAGE_PREFIX,
    CALLBACK_ADMIN_TASKS_BACK_PANEL,
    CALLBACK_ADMIN_TASK_MODERATE_PREFIX,
    MSG_ACCESS_DENIED,
    MSG_ADMIN_REQUEST_NOT_FOUND,
    MSG_ADMIN_TASK_IDENTIFY_ERROR,
    MSG_ADMIN_TASK_USER_NOT_FOUND_ERROR,
    MSG_NO_TASKS_INFO_TO_DISPLAY,
    MSG_ITEM_MESSAGE_DIVIDER,
)


logger = setup_logger(__name__)

admin_tasks_router = Router(name="admin_tasks_router")


def get_admin_tasks_pagination_keyboard(page: int, total_pages: int) -> Optional[InlineKeyboardMarkup]:
    builder = InlineKeyboardBuilder()
    prev_button: Optional[InlineKeyboardButton] = None
    if page > 1:
        prev_button = InlineKeyboardButton(
            text=BTN_PREVIOUS_PAGE, callback_data=f"{CALLBACK_ADMIN_TASKS_PAGE_PREFIX}:{page - 1}"
        )

    next_button: Optional[InlineKeyboardButton] = None
    if page < total_pages:
        next_button = InlineKeyboardButton(
            text=BTN_NEXT_PAGE, callback_data=f"{CALLBACK_ADMIN_TASKS_PAGE_PREFIX}:{page + 1}"
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
                text=f"Review Task ({req_id})", callback_data=f"{CALLBACK_ADMIN_TASK_MODERATE_PREFIX}:{req_id}"
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
        InlineKeyboardButton(text=BTN_BACK_TO_ADMIN_PANEL, callback_data=CALLBACK_ADMIN_TASKS_BACK_PANEL)
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


@admin_tasks_router.callback_query(F.data.startswith(CALLBACK_ADMIN_TASKS_PAGE_PREFIX + ":"), IsAdminFilter())
async def admin_tasks_page_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    acting_user_id = callback_query.from_user.id
    page = 1
    try:
        page_str = callback_query.data.split(":")[1]
        page = int(page_str)
    except (IndexError, ValueError):
        logger.warning(f"invalid page number in admin_tasks_page_cb: {callback_query.data}")
        await callback_query.answer("Error: Invalid page reference.", show_alert=True)
        return

    await callback_query.answer()
    await list_admin_tasks(
        message_to_edit=callback_query.message, acting_user_id=acting_user_id, bot=bot, state=state, page=page
    )


@admin_tasks_router.callback_query(F.data == CALLBACK_ADMIN_TASKS_BACK_PANEL, IsAdminFilter())
async def admin_tasks_back_panel_cb(callback_query: CallbackQuery, bot: Bot):
    await callback_query.answer()
    await show_admin_panel(callback_query, bot)


@admin_tasks_router.callback_query(F.data.startswith(CALLBACK_ADMIN_TASK_MODERATE_PREFIX + ":"), IsAdminFilter())
async def admin_task_moderate_trigger_cb(callback_query: CallbackQuery, bot: Bot):
    action_parts = callback_query.data.split(":")
    if len(action_parts) < 2:
        logger.error(f"Invalid callback data format: {callback_query.data}")
        await callback_query.answer(MSG_ADMIN_TASK_IDENTIFY_ERROR, show_alert=True)
        return

    try:
        request_id = int(action_parts[1])
    except ValueError:
        logger.error(f"invalid request_id in moderate callback: {action_parts[1]}")
        await callback_query.message.reply(Text(MSG_ADMIN_TASK_IDENTIFY_ERROR).as_markdown(), parse_mode="MarkdownV2")
        await callback_query.answer()
        return

    db_request_row = await db.get_request_by_id(request_id)
    if not db_request_row:
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
    if db_request_dict["request_type"] == "problem":
        admin_keyboard = get_admin_report_action_keyboard(request_id)
    else:
        admin_keyboard = get_admin_request_action_keyboard(request_id)
    await bot.send_message(
        chat_id=callback_query.from_user.id,
        text=admin_msg_obj.as_markdown(),
        parse_mode="MarkdownV2",
        reply_markup=admin_keyboard,
    )
