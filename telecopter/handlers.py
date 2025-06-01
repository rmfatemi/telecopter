import asyncio
from typing import Optional, List, Union

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, User as AiogramUser
from aiogram.filters import Command, CommandStart, StateFilter, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.formatting import Text, Bold, Italic, Code, as_list

from telecopter.config import (
    ADMIN_CHAT_ID, TMDB_API_KEY, DEFAULT_PAGE_SIZE,
    MAX_NOTE_LENGTH, MAX_REPORT_LENGTH
)
from telecopter.logger import setup_logger
import telecopter.database as db
import telecopter.tmdb as tmdb_api
from telecopter.utils import (
    format_media_details_for_user,
    truncate_text,
    format_request_for_admin,
)


logger = setup_logger("handlers")
main_router = Router(name="main_router")


class RequestMediaStates(StatesGroup):
    select_media = State()
    confirm_media = State()
    typing_user_note = State()


class ReportProblemStates(StatesGroup):
    typing_problem = State()


class AdminInteractionStates(StatesGroup):
    typing_admin_note = State()


async def _register_user_if_not_exists(aiogram_user: Optional[AiogramUser], chat_id: int):
    if aiogram_user:
        await db.add_or_update_user(
            user_id=aiogram_user.id,
            chat_id=chat_id,
            username=aiogram_user.username,
            first_name=aiogram_user.first_name
        )
        logger.debug("user %s (chat_id: %s) registration/update processed.", aiogram_user.id, chat_id)
    else:
        logger.warning("could not register user, aiogram user object is none for chat_id %s.", chat_id)


def _is_admin(chat_id: int) -> bool:
    if not ADMIN_CHAT_ID:
        logger.warning("admin_chat_id not configured. admin check will always be false.")
        return False
    return chat_id == ADMIN_CHAT_ID


async def _notify_admin(bot: Bot, formatted_text_object: Text, keyboard: Optional[InlineKeyboardMarkup] = None):
    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=formatted_text_object.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error("failed to send notification to admin %s: %s", ADMIN_CHAT_ID, e)
    else:
        logger.warning("admin_chat_id not configured. cannot send admin notification.")


def get_tmdb_select_keyboard(search_results: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in search_results:
        year = f" ({item['year']})" if item.get('year') else ""
        button_text = f"{item['title']}{year}"
        callback_data = f"tmdb_sel:{item['tmdb_id']}:{item['media_type']}"
        builder.button(text=button_text, callback_data=callback_data)
    builder.button(text="Cancel Request", callback_data=f"tmdb_sel:action_cancel")
    builder.adjust(1)
    return builder.as_markup()


def get_request_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Yes, Request It", callback_data=f"req_conf:yes")
    builder.button(text="Yes, With a Note", callback_data=f"req_conf:yes_note")
    builder.button(text="No, Cancel", callback_data=f"req_conf:action_cancel")
    builder.adjust(1)
    return builder.as_markup()


def get_admin_request_action_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    actions_media = {
        f"approve": "Approve",
        f"approve_with_note": "Approve w/ Note",
        f"deny": "Deny",
        f"deny_with_note": "Deny w/ Note",
        f"complete": "Mark Completed",
        f"complete_with_note": "Complete w/ Note",
    }
    for action_key, text in actions_media.items():
        builder.button(text=text, callback_data=f"admin_act:{action_key}:{request_id}")
    builder.adjust(2)
    return builder.as_markup()


def get_admin_report_action_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    actions_report = {
        f"acknowledge": "Acknowledge",
        f"complete": "Mark Resolved",
        f"complete_with_note": "Resolve w/ Note",
    }
    for action_key, text in actions_report.items():
        builder.button(text=text, callback_data=f"admin_act:{action_key}:{request_id}")
    builder.adjust(1)
    return builder.as_markup()


def get_my_requests_pagination_keyboard(page: int, total_pages: int) -> Optional[InlineKeyboardMarkup]:
    builder = InlineKeyboardBuilder()
    if page > 1:
        builder.button(text="⬅️ Previous", callback_data=f"my_req_page:{page - 1}")
    if page < total_pages:
        builder.button(text="Next ➡️", callback_data=f"my_req_page:{page + 1}")
    if builder.buttons:
        builder.adjust(2)
        return builder.as_markup()
    return None


@main_router.message(Command("cancel"), StateFilter("*"))
@main_router.callback_query(F.data == "action_cancel", StateFilter("*"))
async def universal_cancel_handler(event: Message | CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        logger.info("user %s cancelled conversation from state %s.", event.from_user.id, current_state)
        await state.clear()
    else:
        logger.info("user %s used /cancel outside of a conversation.", event.from_user.id)

    cancel_message = "Action cancelled."
    if isinstance(event, Message):
        await event.answer(cancel_message)
    elif isinstance(event, CallbackQuery):
        await event.answer("Action cancelled.", show_alert=False)
        try:
            if event.message:
                await event.message.edit_text(cancel_message, reply_markup=None)
        except Exception as e:
            logger.debug("failed to edit message on cancel, possibly unchanged or deleted: %s", e)
            if event.message and event.message.chat:
                await event.message.chat.ask(cancel_message, bot=event.bot)  # type: ignore


@main_router.message(CommandStart())
async def start_command_handler(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user:
        await _register_user_if_not_exists(message.from_user, message.chat.id)
        welcome_text = (
            f"Hello {message.from_user.first_name}!\n\n"
            "I am Telecopter, your friendly media request bot.\n\n"
            "You can use me to:\n"
            "🎬 `/request <movie or tv show name>` - Request new media.\n"
            "📊 `/my_requests` - View the status of your past requests.\n"
            "⚠️ `/report <problem description>` - Report an issue.\n\n"
            "Use `/help` to see this message again."
        )
        await message.answer(welcome_text, parse_mode=None)


@main_router.message(Command("help"))
async def help_command_handler(message: Message, state: FSMContext):
    await state.clear()
    help_text = (
        "Here's how you can use me:\n\n"
        "🎬 `/request <movie or tv show name>`\n"
        "   Searches for the media and lets you confirm your request.\n\n"
        "📊 `/my_requests`\n"
        "   Shows a list of your previous media requests and problem reports, along with their status.\n\n"
        "⚠️ `/report <problem description>`\n"
        "   Allows you to report any problems you encounter (e.g., issues with existing media, bot problems, etc.).\n\n"
        "If you are the admin, you also have access to other commands and will receive notifications."
    )
    await message.answer(help_text, parse_mode=None)


@main_router.message(Command("request"))
async def request_command_entry_handler(message: Message, command: CommandObject, state: FSMContext):
    if not message.from_user: return
    await _register_user_if_not_exists(message.from_user, message.chat.id)

    if not TMDB_API_KEY:
        await message.answer("Media search is currently unavailable.")
        return

    query_text = command.args
    if not query_text:
        await message.answer("Please provide the name of the movie or TV show. Usage: `/request <name>`")
        return

    logger.info("user %s initiated /request with query: %s", message.from_user.id, query_text)
    await state.update_data({"request_query": query_text})

    search_results = await tmdb_api.search_media(query_text)

    if not search_results:
        await message.answer(
            f"Sorry, I couldn't find any results for '{query_text}'. Please check spelling or try again.",
            parse_mode=None)
        return

    text_parts = ["I found these results. Please select one:\n"]
    for i, item in enumerate(search_results):
        year = f" ({item['year']})" if item.get('year') else ""
        text_parts.append(f"{i + 1}. {item['title']}{year} [{item['media_type']}]")

    await message.answer("\n".join(text_parts), reply_markup=get_tmdb_select_keyboard(search_results), parse_mode=None)
    await state.set_state(RequestMediaStates.select_media)


@main_router.callback_query(StateFilter(RequestMediaStates.select_media), F.data.startswith("tmdb_sel:"))
async def select_media_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message: return

    data_parts = callback_query.data.split(":")
    action = data_parts[1]

    if action == "action_cancel":
        await callback_query.message.edit_text("Request cancelled.", reply_markup=None)
        await state.clear()
        return

    tmdb_id = int(action)
    media_type = data_parts[2]

    media_details = await tmdb_api.get_media_details(tmdb_id, media_type)
    if not media_details:
        await callback_query.message.edit_text("Sorry, I couldn't fetch details for your selection. Please try again.",
                                               reply_markup=None)
        await state.clear()
        return

    await state.update_data({"selected_media_details": media_details})

    formatted_details_obj = format_media_details_for_user(media_details)
    caption_text_md = formatted_details_obj.as_markdown() + "\n\nDo you want to request this?"

    keyboard = get_request_confirm_keyboard()

    try:
        if media_details.get('poster_url'):
            await callback_query.bot.send_photo(
                chat_id=callback_query.message.chat.id,
                photo=media_details['poster_url'],
                caption=caption_text_md,
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            await callback_query.message.delete()
        else:
            await callback_query.message.edit_text(caption_text_md, reply_markup=keyboard, parse_mode="MarkdownV2")
    except Exception as e:
        logger.warning("error sending media confirmation photo/text: %s. falling back to simple text edit.", e)
        await callback_query.message.edit_text(caption_text_md, reply_markup=keyboard, parse_mode="MarkdownV2")

    await state.set_state(RequestMediaStates.confirm_media)


@main_router.callback_query(StateFilter(RequestMediaStates.confirm_media), F.data.startswith("req_conf:"))
async def confirm_media_request_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message: return

    action = callback_query.data.split(":")[1]
    user_fsm_data = await state.get_data()
    selected_media = user_fsm_data.get("selected_media_details")

    if not selected_media:
        await callback_query.message.edit_text("Error: Your selection expired. Please start over.", reply_markup=None)
        await state.clear()
        return

    if action == "action_cancel":
        await callback_query.message.edit_text("Request cancelled.", reply_markup=None)
        await state.clear()
        return

    if action == "yes_note":
        await callback_query.message.edit_text("Please send me a short note for your request.", reply_markup=None)
        await state.set_state(RequestMediaStates.typing_user_note)
        return

    request_id = await db.add_media_request(
        user_id=callback_query.from_user.id,
        tmdb_id=selected_media['tmdb_id'],
        title=selected_media['title'],
        year=selected_media.get('year'),
        imdb_id=selected_media.get('imdb_id'),
        request_type=selected_media['media_type'],
        user_query=user_fsm_data.get("request_query"),
        user_note=None
    )
    await callback_query.message.edit_text(
        "Your request has been submitted to the admin for review. You'll be notified of updates.",
        reply_markup=None
    )

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(callback_query.from_user.id)
    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_kb = get_admin_request_action_keyboard(request_id) if db_request_row[
                                                                        'request_type'] != "problem" else get_admin_report_action_keyboard(
            request_id)
        await _notify_admin(callback_query.bot, admin_msg_obj, admin_kb)

    await state.clear()


@main_router.message(StateFilter(RequestMediaStates.typing_user_note), F.text)
async def user_note_handler(message: Message, state: FSMContext):
    if not message.from_user or not message.text: return

    user_fsm_data = await state.get_data()
    selected_media = user_fsm_data.get("selected_media_details")

    if not selected_media:
        await message.answer("Error: Your selection seems to have expired. Please start the request over.")
        await state.clear()
        return

    note_text = truncate_text(message.text, MAX_NOTE_LENGTH)
    request_id = await db.add_media_request(
        user_id=message.from_user.id,
        tmdb_id=selected_media['tmdb_id'],
        title=selected_media['title'],
        year=selected_media.get('year'),
        imdb_id=selected_media.get('imdb_id'),
        request_type=selected_media['media_type'],
        user_query=user_fsm_data.get("request_query"),
        user_note=note_text
    )
    await message.answer("Your request with the note has been submitted. You'll be notified of updates.")

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(message.from_user.id)
    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_kb = get_admin_request_action_keyboard(request_id) if db_request_row[
                                                                        'request_type'] != "problem" else get_admin_report_action_keyboard(
            request_id)
        await _notify_admin(message.bot, admin_msg_obj, admin_kb)

    await state.clear()


@main_router.message(Command("report"))
async def report_command_entry_handler(message: Message, command: CommandObject, state: FSMContext):
    if not message.from_user: return
    await _register_user_if_not_exists(message.from_user, message.chat.id)

    problem_description = command.args
    if not problem_description:
        await message.answer(
            "Please describe the problem. Usage: `/report <description>`\nOr just send your problem description now.")
        await state.set_state(ReportProblemStates.typing_problem)
        return

    await _submit_problem_report_logic(message, problem_description, state)


@main_router.message(StateFilter(ReportProblemStates.typing_problem), F.text)
async def problem_report_text_handler(message: Message, state: FSMContext):
    if not message.text: return
    await _submit_problem_report_logic(message, message.text, state)


async def _submit_problem_report_logic(message: Message, problem_text: str, state: FSMContext):
    if not message.from_user: return

    problem_text_truncated = truncate_text(problem_text, MAX_REPORT_LENGTH)
    request_id = await db.add_problem_report(message.from_user.id, problem_text_truncated)

    await message.answer("Your problem report has been submitted. Thank you!")
    logger.info("user %s submitted problem report id %s: %s", message.from_user.id, request_id,
                problem_text_truncated[:50])

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(message.from_user.id)
    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_kb = get_admin_report_action_keyboard(request_id)
        await _notify_admin(message.bot, admin_msg_obj, admin_kb)
    await state.clear()


@main_router.message(Command("my_requests"))
async def my_requests_command_handler(message: Message, state: FSMContext):
    if not message.from_user: return
    await _register_user_if_not_exists(message.from_user, message.chat.id)
    await _send_my_requests_page_logic(message.from_user.id, 1, message.chat.id, message.bot,
                                       original_message_id=message.message_id, is_callback=False)


@main_router.callback_query(F.data.startswith("my_req_page:"))
async def my_requests_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message: return

    page = int(callback_query.data.split(":")[1])
    await _send_my_requests_page_logic(callback_query.from_user.id, page, callback_query.message.chat.id,
                                       callback_query.bot, original_message_id=callback_query.message.message_id,
                                       is_callback=True)


async def _send_my_requests_page_logic(user_id: int, page: int, chat_id: int, bot: Bot, original_message_id: int,
                                       is_callback: bool):
    requests_rows = await db.get_user_requests(user_id, page, DEFAULT_PAGE_SIZE)
    total_requests = await db.get_user_requests_count(user_id)
    total_pages = (total_requests + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
    total_pages = max(1, total_pages)

    page_content: List[Union[str, Text, Bold, Italic, Code]] = []

    if not requests_rows and page == 1:
        page_content.append(Text("You haven't made any requests or reports yet."))
    elif not requests_rows and page > 1:
        page_content.append(Text("No more requests found on this page."))
    else:
        page_content.append(Bold(f"Your Requests & Reports (Page {page} of {total_pages})"))
        page_content.append(Text("\n"))

        for req_row in requests_rows:
            req = dict(req_row)
            title_disp = truncate_text(req['title'], 50)
            req_type_icon = "🎬" if req['request_type'] in ["movie", "tv"] else "⚠️"
            date_req = req['created_at'][:10]

            request_item_elements: list[Union[str, Text, Bold, Italic, Code]] = [
                Text(req_type_icon, " "), Bold(title_disp), Text("\n"),
                Text("   Status: "), Italic(req['status']), Text(", Requested: "), Text(date_req), Text("\n")
            ]
            if req.get('user_note'):
                request_item_elements.extend([
                    Text("   Your Note: "), Italic(truncate_text(req['user_note'], 70)), Text("\n")
                ])
            if req.get('admin_note'):
                request_item_elements.extend([
                    Text("   Admin Note: "), Italic(truncate_text(req['admin_note'], 70)), Text("\n")
                ])
            request_item_elements.append(Text("---"))
            page_content.append(as_list(*request_item_elements, sep=""))
            page_content.append(Text("\n"))

    final_text_object = as_list(*page_content, sep="") if page_content else Text("No requests to display.")
    keyboard = get_my_requests_pagination_keyboard(page, total_pages)
    text_to_send = final_text_object.as_markdown()

    if is_callback:
        try:
            await bot.edit_message_text(
                text=text_to_send,
                chat_id=chat_id,
                message_id=original_message_id,
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.debug("failed to edit /my_requests page: %s", e)
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=text_to_send,
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )


@main_router.callback_query(F.data.startswith("admin_act:"))
async def admin_action_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message: return

    if not _is_admin(callback_query.from_user.id):
        await callback_query.message.reply("This action is admin-only.", parse_mode=None)
        return

    try:
        parts = callback_query.data.split(":")
        action_full_key = parts[1]
        request_id = int(parts[2])
    except (IndexError, ValueError):
        logger.error("invalid admin action callback data: %s", callback_query.data)
        await callback_query.message.edit_text("Sorry, an unexpected error occurred. Please try again later.",
                                               reply_markup=None)
        return

    original_request_row = await db.get_request_by_id(request_id)
    if not original_request_row:
        await callback_query.message.edit_text(f"Error: Request ID {request_id} not found.", reply_markup=None)
        return
    original_request = dict(original_request_row)

    base_action_key = action_full_key.replace("_with_note", "")

    if "_with_note" in action_full_key:
        await state.set_state(AdminInteractionStates.typing_admin_note)
        await state.update_data({
            "admin_request_id": request_id,
            "admin_base_action": base_action_key
        })
        await callback_query.message.edit_text(
            f"Please send the note for Request ID {request_id} to be {base_action_key}d.", reply_markup=None)
        return

    new_status: Optional[str] = None
    user_notification_text_template: Optional[str] = None

    if base_action_key == "approve":
        new_status = "approved"
        user_notification_text_template = "Great news! Your request for \"{title}\" has been approved."
    elif base_action_key == "deny":
        new_status = "denied"
        user_notification_text_template = "Regarding your request for \"{title}\", the admin has denied it."
    elif base_action_key == "complete":
        new_status = "completed"
        if original_request['request_type'] == "problem":
            user_notification_text_template = "Update: Your problem report \"{title}\" has been marked as resolved."
        else:
            user_notification_text_template = "Update: Your request for \"{title}\" is now completed and available!"
    elif base_action_key == "acknowledge":
        new_status = "acknowledged"
        user_notification_text_template = "Update: Your problem report \"{title}\" has been acknowledged by the admin."

    admin_confirm_msg = "Sorry, an unexpected error occurred. Please try again later."
    if new_status and user_notification_text_template:
        success = await db.update_request_status(request_id, new_status, admin_note=None)
        if success:
            admin_confirm_msg = f"Request ID {request_id} status set to {new_status}. User notified."
            await db.log_admin_action(callback_query.from_user.id, action_full_key, request_id=request_id)

            submitter_chat_id = await db.get_request_submitter_chat_id(request_id)
            if submitter_chat_id:
                user_msg = user_notification_text_template.format(title=original_request['title'])
                try:
                    await bot.send_message(submitter_chat_id, user_msg, parse_mode=None)
                except Exception as e:
                    logger.error("failed to send status update to user for request %s: %s", request_id, e)
        else:
            admin_confirm_msg = f"Failed to update status for Request ID {request_id} to {new_status}."
    else:
        admin_confirm_msg = f"Unknown action '{action_full_key}' for Request ID {request_id}."

    await callback_query.message.edit_text(admin_confirm_msg, reply_markup=None)


@main_router.message(StateFilter(AdminInteractionStates.typing_admin_note), F.text)
async def admin_note_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text: return

    fsm_data = await state.get_data()
    request_id = fsm_data.get("admin_request_id")
    base_action = fsm_data.get("admin_base_action")
    admin_note_text = truncate_text(message.text, MAX_NOTE_LENGTH)

    if not request_id or not base_action:
        await message.answer("Error: Could not retrieve context for adding note. Please try the action again.")
        await state.clear()
        return

    original_request_row = await db.get_request_by_id(request_id)
    if not original_request_row:
        await message.answer(f"Error: Request ID {request_id} not found.")
        await state.clear()
        return
    original_request = dict(original_request_row)

    new_status: Optional[str] = None
    user_notification_text_template: Optional[str] = None

    if base_action == "approve":
        new_status = "approved"; user_notification_text_template = "Great news! Your request for \"{title}\" has been approved by the admin."
    elif base_action == "deny":
        new_status = "denied"; user_notification_text_template = "Regarding your request for \"{title}\", the admin has denied it."
    elif base_action == "complete":
        new_status = "completed"
        if original_request['request_type'] == "problem":
            user_notification_text_template = "Update: Your problem report \"{title}\" has been marked as resolved by the admin."
        else:
            user_notification_text_template = "Update: Your request for \"{title}\" has been completed by the admin."

    admin_confirm_msg = "Sorry, an unexpected error occurred. Please try again later."
    if new_status and user_notification_text_template:
        success = await db.update_request_status(request_id, new_status, admin_note=admin_note_text)
        if success:
            full_action_key = f"{base_action}_with_note"
            admin_confirm_msg = f"Request ID {request_id} has been {base_action}d with your note. User notified."
            await db.log_admin_action(message.from_user.id, full_action_key, request_id=request_id,
                                      details=admin_note_text)

            submitter_chat_id = await db.get_request_submitter_chat_id(request_id)
            if submitter_chat_id:
                user_msg_obj = Text(
                    user_notification_text_template.format(title=original_request['title']),
                    "\n\n",  # Explicit newline Text object
                    Bold("Admin's note:"), " ", Italic(admin_note_text)
                )
                try:
                    await bot.send_message(submitter_chat_id, text=user_msg_obj.as_markdown(), parse_mode="MarkdownV2")
                except Exception as e:
                    logger.error("failed to send status update with admin note to user for req %s: %s", request_id, e)
        else:
            admin_confirm_msg = f"Failed to update Request ID {request_id} with your note."
    else:
        admin_confirm_msg = f"Error processing admin action '{base_action}' with note for Request ID {request_id}."

    await message.answer(admin_confirm_msg)
    await state.clear()


@main_router.message(Command("announce", "announce_muted"))
async def announce_command_handler(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("This command is admin-only.")
        return

    if not command.args:
        await message.reply(f"Please provide a message. Usage: `/{command.command} <message>`")
        return

    announcement_text = command.args  # This is plain text from admin
    is_muted = command.command == "announce_muted"

    # Construct the message using Text objects for safety with MarkdownV2
    formatted_announcement = Text(
        Bold("📢 Announcement from Admin:"),
        "\n\n",  # Explicit newline Text object for spacing
        Text(announcement_text)  # Treat the announcement text as plain
    )

    chat_ids = await db.get_all_user_chat_ids()
    if not chat_ids:
        await message.reply("No registered users found.")
        return

    sent_count = 0
    failed_count = 0
    for cid in chat_ids:
        try:
            await bot.send_message(
                chat_id=cid,
                text=formatted_announcement.as_markdown(),
                parse_mode="MarkdownV2",
                disable_notification=is_muted
            )
            sent_count += 1
        except Exception as e:
            logger.error("failed to send announcement to chat_id %s: %s", cid, e)
            failed_count += 1
        await asyncio.sleep(0.1)

    response_text = f"Announcement sent to {sent_count} users."
    if failed_count > 0:
        response_text += f" {failed_count} failures."
    await message.reply(response_text)

    await db.log_admin_action(
        admin_user_id=message.from_user.id,
        action="announce_muted" if is_muted else "announce",
        details=f"Sent: {sent_count}, Failed: {failed_count}. Msg: {announcement_text[:100]}"
    )
