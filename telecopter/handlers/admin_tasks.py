from typing import List, Union, Optional

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.formatting import Text, Bold, Italic, Code, as_list
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import DEFAULT_PAGE_SIZE
from telecopter.handlers.common_utils import is_admin
from telecopter.utils import truncate_text, format_request_for_admin
from telecopter.handlers.admin_moderate import get_admin_request_action_keyboard, get_admin_report_action_keyboard


logger = setup_logger(__name__)

admin_tasks_router = Router(name="admin_tasks_router")


def get_admin_tasks_pagination_keyboard(page: int, total_pages: int) -> Optional[InlineKeyboardMarkup]:
    builder = InlineKeyboardBuilder()
    if page > 1:
        builder.button(text="⬅️ previous tasks", callback_data=f"admin_tasks_page:{page - 1}")
    if page < total_pages:
        builder.button(text="next tasks ➡️", callback_data=f"admin_tasks_page:{page + 1}")
    if builder.buttons:
        builder.adjust(2)
        return builder.as_markup()
    return None


async def list_admin_tasks(
        message_to_edit: Message,
        acting_user_id: int,
        bot: Bot,
        state: FSMContext,
        page: int = 1
):
  
    if not await is_admin(acting_user_id, bot):
        logger.warning("list_admin_tasks called by non-admin user %s or without privileges.", acting_user_id)
        if message_to_edit.chat:
            denied_text_obj = Text("access denied.")
          
            await bot.send_message(message_to_edit.chat.id, denied_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    await state.clear()
  
    requests_rows = await db.get_actionable_admin_requests(page, DEFAULT_PAGE_SIZE)
    total_requests = await db.get_actionable_admin_requests_count()
    total_pages = (total_requests + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
    total_pages = max(1, total_pages)

    content_elements: List[Union[Text, Bold, Italic, Code]] = []
    tasks_keyboard_builder = InlineKeyboardBuilder()

    if not requests_rows and page == 1:
        content_elements.append(Text("🎉 no pending tasks for admins at the moment!"))
    elif not requests_rows and page > 1:
        content_elements.append(Text(f"✅ no more tasks found on page {page}."))
    else:
        content_elements.append(Bold(f"📋 admin tasks (page {page} of {total_pages})"))
        content_elements.append(Text("\n"))

        for req_row in requests_rows:
            req = dict(req_row)
            title_disp = truncate_text(req["title"], 35)
            req_type_icon = "🎬" if req["request_type"] in ["movie", "tv", "manual_media"] else "⚠️"
            user_db_info = await db.get_user(req["user_id"])
            user_name_disp = user_db_info['username'] or user_db_info['first_name'] if user_db_info else "unknown user"
            created_date = req["created_at"][:10]

            item_text_str = f"{req_type_icon} id:{req['request_id']} - {title_disp} ({req['status']})\nby {user_name_disp} on {created_date}"
            content_elements.append(Text(item_text_str))

            tasks_keyboard_builder.button(
                text=f"mod id:{req['request_id']}",
                callback_data=f"admin_task_moderate:{req['request_id']}"
            )
            content_elements.append(Text("---"))

        tasks_keyboard_builder.adjust(1)

    pagination_kb_markup = get_admin_tasks_pagination_keyboard(page, total_pages)
    if pagination_kb_markup:
        for row_buttons in pagination_kb_markup.inline_keyboard:
            tasks_keyboard_builder.row(*row_buttons)

    tasks_keyboard_builder.row(
        InlineKeyboardButton(text="⬅️ back to admin panel", callback_data="admin_tasks_back_panel"))

    final_text_content_obj = as_list(*content_elements, sep="\n") if content_elements else Text(
        "no tasks information to display.")
    reply_markup = tasks_keyboard_builder.as_markup()

    try:
        await message_to_edit.edit_text(final_text_content_obj.as_markdown(), parse_mode="MarkdownV2",
                                        reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"failed to edit admin tasks message: {e}, sending new.")
        if message_to_edit.chat:
            await bot.send_message(message_to_edit.chat.id, final_text_content_obj.as_markdown(),
                                   parse_mode="MarkdownV2", reply_markup=reply_markup)


@admin_tasks_router.callback_query(F.data.startswith("admin_tasks_page:"))
async def admin_tasks_page_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    if not callback_query.from_user or not callback_query.message:
        await callback_query.answer("error processing request.", show_alert=True)
        return

    acting_user_id = callback_query.from_user.id

    page = 1
    try:
        page = int(callback_query.data.split(":")[1])
    except (IndexError, ValueError):
        logger.warning(f"invalid page number in admin_tasks_page_cb: {callback_query.data}")

    await callback_query.answer()
    await list_admin_tasks(
        message_to_edit=callback_query.message,
        acting_user_id=acting_user_id,
        bot=bot,
        state=state,
        page=page
    )


@admin_tasks_router.callback_query(F.data == "admin_tasks_back_panel")
async def admin_tasks_back_panel_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    from .admin_panel import show_admin_panel
    if not callback_query.from_user or not await is_admin(callback_query.from_user.id, bot):
        await callback_query.answer("access denied.", show_alert=True)
        return
    await callback_query.answer()
    await show_admin_panel(callback_query, bot)


@admin_tasks_router.callback_query(F.data.startswith("admin_task_moderate:"))
async def admin_task_moderate_trigger_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    if not callback_query.from_user or not await is_admin(callback_query.from_user.id, bot):
        await callback_query.answer("access denied.", show_alert=True)
        return
    await callback_query.answer()
    request_id_str = callback_query.data.split(":")[1]

    try:
        request_id = int(request_id_str)
    except ValueError:
        logger.error(f"invalid request_id in admin_task_moderate callback: {request_id_str}")
        if callback_query.message and callback_query.message.chat:
            error_text_obj = Text("error: could not identify the task.")
            await bot.send_message(callback_query.message.chat.id, error_text_obj.as_markdown(),
                                   parse_mode="MarkdownV2")
        return

    db_request_row = await db.get_request_by_id(request_id)
    if not db_request_row:
        if callback_query.message and callback_query.message.chat:
            error_text_obj = Text(f"error: task id {request_id} not found.")
            await bot.send_message(callback_query.message.chat.id, error_text_obj.as_markdown(),
                                   parse_mode="MarkdownV2")
        return

    db_user_row = await db.get_user(db_request_row["user_id"])
    if not db_user_row:
        if callback_query.message and callback_query.message.chat:
            error_text_obj = Text(f"error: user for task id {request_id} not found.")
            await bot.send_message(callback_query.message.chat.id, error_text_obj.as_markdown(),
                                   parse_mode="MarkdownV2")
        return

    admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
    admin_keyboard = None
    if db_request_row["request_type"] == "problem":
        admin_keyboard = get_admin_report_action_keyboard(request_id)
    else:
        admin_keyboard = get_admin_request_action_keyboard(request_id)

    await bot.send_message(
        chat_id=callback_query.from_user.id,
        text=admin_msg_obj.as_markdown(),
        parse_mode="MarkdownV2",
        reply_markup=admin_keyboard
    )
