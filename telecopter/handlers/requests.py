from typing import Optional, List, Union

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import StateFilter
from aiogram.utils.formatting import Text, Bold, Italic, Code, as_list
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import telecopter.database as db
import telecopter.tmdb as tmdb_api
from telecopter.logger import setup_logger
from telecopter.config import MAX_NOTE_LENGTH, DEFAULT_PAGE_SIZE
from telecopter.utils import format_media_details_for_user, truncate_text, format_request_for_admin

logger = setup_logger(__name__)

requests_router = Router(name="requests_router")


class RequestMediaStates(StatesGroup):
    typing_media_name = State()
    select_media = State()
    typing_manual_request_description = State()
    confirm_media = State()
    typing_user_note = State()


def get_tmdb_select_keyboard(search_results: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in search_results:
        year = f" ({item['year']})" if item.get('year') else ""
        media_emoji = "🎬" if item['media_type'] == 'movie' else "📺" if item['media_type'] == 'tv' else "❔"
        button_text = f"{media_emoji} {item['title']}{year}"
        callback_data = f"tmdb_sel:{item['tmdb_id']}:{item['media_type']}"
        builder.button(text=truncate_text(button_text, 60), callback_data=callback_data)
    builder.button(text="📝 Other / Not Found - Manual Request", callback_data="tmdb_sel:manual_request")
    builder.button(text="❌ Cancel Request", callback_data="tmdb_sel:action_cancel")
    builder.adjust(1)
    return builder.as_markup()


def get_request_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yes, request it", callback_data="req_conf:yes")
    builder.button(text="📝 Yes, with a note", callback_data="req_conf:yes_note")
    builder.button(text="❌ No, cancel", callback_data="req_conf:action_cancel")
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


@requests_router.message(StateFilter(RequestMediaStates.typing_media_name), F.text)
async def process_media_name_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        await message.answer("✍️ Please type the name of the media you're looking for, or use /cancel to exit.")
        return

    query_text = message.text.strip()
    if not query_text:
        await message.answer("✍️ The media name cannot be empty. Please type a valid name, or use /cancel.")
        return
    if len(query_text) < 2:
        await message.answer("✍️ Your search query is too short. Please try a more specific name, or use /cancel.")
        return

    logger.info("user %s initiated request with query: %s", message.from_user.id, query_text)
    await state.update_data({"request_query": query_text})
    searching_msg = await message.answer(f"🔎 Searching for \"{query_text}\"...")

    search_results = await tmdb_api.search_media(query_text)

    try:
        await bot.delete_message(chat_id=searching_msg.chat.id, message_id=searching_msg.message_id)
    except Exception:
        logger.debug(
            "could not delete 'searching...' message, it might have already been deleted or bot lacks permission.")

    if not search_results:
        await message.answer(
            f"😕 Sorry, I couldn't find any results for \"{query_text}\".\n"
            f"You can try a different name, select 'Other / Not Found' from a previous search (if applicable), or use /cancel to exit.",
            reply_markup=get_tmdb_select_keyboard([])
        )
        return

    await message.answer(f"🔍 Here's what I found for \"{query_text}\". Please select one:",
                         reply_markup=get_tmdb_select_keyboard(search_results))
    await state.set_state(RequestMediaStates.select_media)


@requests_router.callback_query(StateFilter(RequestMediaStates.select_media), F.data.startswith("tmdb_sel:"))
async def select_media_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message: return

    action_data = callback_query.data

    if action_data == "tmdb_sel:action_cancel":
        try:
            await callback_query.message.edit_text("✅ Request process cancelled.", reply_markup=None)
        except TelegramBadRequest:
            await callback_query.message.delete()
            await bot.send_message(callback_query.message.chat.id, "✅ Request process cancelled.")
        await state.clear()
        from telecopter.handlers.common import _show_main_menu
        await _show_main_menu(callback_query.message, "✅ Request cancelled. What can I help you with next?")
        return

    if action_data == "tmdb_sel:manual_request":
        user_fsm_data = await state.get_data()
        original_query = user_fsm_data.get("request_query", "your previous search")
        await callback_query.message.edit_text(
            f"✍️ Okay, you didn't find an exact match or chose 'Other'.\n"
            f"Please describe the media you're looking for (e.g., title, year, any details). "
            f"Your original search term was: \"{original_query}\".\nThis will be sent as a manual request.",
            reply_markup=None
        )
        await state.set_state(RequestMediaStates.typing_manual_request_description)
        return

    try:
        data_prefix, tmdb_id_str, media_type = action_data.split(":", 2)
        if data_prefix != "tmdb_sel":
            raise ValueError("incorrect prefix")
        tmdb_id = int(tmdb_id_str)
    except ValueError:
        logger.error("invalid callback data format for tmdb selection: %s", action_data)
        try:
            await callback_query.message.edit_text(
                "❗ Oops! An unexpected error occurred. Please try again later or /cancel.",
                reply_markup=None)
        except TelegramBadRequest:
            await callback_query.message.delete()
            await bot.send_message(callback_query.message.chat.id,
                                   "❗ Oops! An unexpected error occurred. Please try again later or /cancel.")
        await state.clear()
        return

    media_details = await tmdb_api.get_media_details(tmdb_id, media_type)
    if not media_details:
        try:
            await callback_query.message.edit_text(
                "🔎❗ Sorry, I couldn't fetch the details for that selection. Please try again or /cancel.",
                reply_markup=None)
        except TelegramBadRequest:
            await callback_query.message.delete()
            await bot.send_message(callback_query.message.chat.id,
                                   "🔎❗ Sorry, I couldn't fetch the details for that selection. Please try again or /cancel.")
        await state.clear()
        return

    await state.update_data({"selected_media_details": media_details})

    formatted_details_obj = format_media_details_for_user(media_details)
    caption_text_md = formatted_details_obj.as_markdown() + "\n\n🎯 Confirm: Do you want to request this?"
    keyboard = get_request_confirm_keyboard()

    try:
        if callback_query.message:
            original_message_chat_id = callback_query.message.chat.id
            await callback_query.message.delete()

            if media_details.get('poster_url'):
                await bot.send_photo(
                    chat_id=original_message_chat_id,
                    photo=media_details['poster_url'],
                    caption=caption_text_md,
                    reply_markup=keyboard,
                    parse_mode="MarkdownV2"
                )
            else:
                await bot.send_message(
                    chat_id=original_message_chat_id,
                    text=caption_text_md,
                    reply_markup=keyboard,
                    parse_mode="MarkdownV2"
                )
    except Exception as e:
        logger.warning(
            "error sending media confirmation photo/text after deleting original: %s. falling back to new message.", e)
        try:
            await bot.send_message(
                chat_id=callback_query.from_user.id,
                text=caption_text_md,
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
        except Exception as e_fallback:
            logger.error("error in fallback sending media confirmation: %s", e_fallback)
            await bot.send_message(callback_query.from_user.id,
                                   "❗ An error occurred showing media details. Please try again or /cancel.")

    await state.set_state(RequestMediaStates.confirm_media)


@requests_router.message(StateFilter(RequestMediaStates.typing_manual_request_description), F.text)
async def manual_request_description_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        await message.answer("✍️ Please provide a description for your manual request, or use /cancel.")
        return

    description = message.text.strip()
    if len(description) < 5:
        await message.answer("✍️ Your description is a bit short. Please provide more details, or use /cancel.")
        return

    user_fsm_data = await state.get_data()
    original_query = user_fsm_data.get("request_query", "not specified")

    request_id = await db.add_media_request(
        user_id=message.from_user.id,
        tmdb_id=None,
        title=description,
        year=None,
        imdb_id=None,
        request_type="manual_media",
        user_query=original_query,
        user_note=None
    )
    await message.answer(
        f"✅ Your manual request for \"{truncate_text(description, 50)}\" has been submitted. Admins will review it.")

    if db_request_row := await db.get_request_by_id(request_id):
        if db_user_row := await db.get_user(message.from_user.id):
            from telecopter.handlers.admin import get_admin_request_action_keyboard
            from telecopter.handlers.common import notify_admin_formatted
            admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
            admin_kb = get_admin_request_action_keyboard(request_id)
            await notify_admin_formatted(bot, admin_msg_obj, admin_kb)

    await state.clear()
    from telecopter.handlers.common import _show_main_menu
    await _show_main_menu(message, "✅ Manual request submitted! What can I help you with next?")


@requests_router.callback_query(StateFilter(RequestMediaStates.confirm_media), F.data.startswith("req_conf:"))
async def confirm_media_request_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message: return

    action = callback_query.data.split(":")[1]
    user_fsm_data = await state.get_data()
    selected_media = user_fsm_data.get("selected_media_details")

    chat_id_to_reply = callback_query.from_user.id

    try:
        await callback_query.message.delete()
    except Exception as e:
        logger.debug("failed to delete confirmation message: %s", e)

    if not selected_media:
        await bot.send_message(chat_id_to_reply,
                               "⏳ Error: Your selection seems to have expired. Please start over.")
        await state.clear()
        from telecopter.handlers.common import _show_main_menu
        await _show_main_menu(callback_query.message,
                              "⏳ Selection expired. What can I help you with next?") if callback_query.message else None
        return

    if action == "action_cancel":
        await bot.send_message(chat_id_to_reply, "✅ Request submission cancelled.")
        await state.clear()
        from telecopter.handlers.common import _show_main_menu
        await _show_main_menu(callback_query.message,
                              "✅ Request cancelled. What can I help you with next?") if callback_query.message else None
        return

    if action == "yes_note":
        await bot.send_message(chat_id_to_reply,
                               "📝 Please send me a short note for your request. You can /cancel if you change your mind.")
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
    await bot.send_message(
        chat_id_to_reply,
        "✅ Your request has been submitted for review. You'll be notified of updates!"
    )

    if db_request_row := await db.get_request_by_id(request_id):
        if db_user_row := await db.get_user(callback_query.from_user.id):
            from telecopter.handlers.admin import get_admin_request_action_keyboard
            from telecopter.handlers.common import notify_admin_formatted
            admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
            admin_kb = get_admin_request_action_keyboard(request_id)
            await notify_admin_formatted(bot, admin_msg_obj, admin_kb)

    await state.clear()
    from telecopter.handlers.common import _show_main_menu
    await _show_main_menu(callback_query.message,
                          "✅ Request submitted! What can I help you with next?") if callback_query.message else None


@requests_router.message(StateFilter(RequestMediaStates.typing_user_note), F.text)
async def user_note_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text: return

    user_fsm_data = await state.get_data()
    selected_media = user_fsm_data.get("selected_media_details")

    if not selected_media:
        await message.answer(
            "⏳ Error: Your selection seems to have expired. Please start the request over.")
        await state.clear()
        from telecopter.handlers.common import _show_main_menu
        await _show_main_menu(message, "⏳ Selection expired. What can I help you with next?")
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
    await message.answer("✅ Your request with the note has been submitted. You'll be notified of updates!")

    if db_request_row := await db.get_request_by_id(request_id):
        if db_user_row := await db.get_user(message.from_user.id):
            from telecopter.handlers.admin import get_admin_request_action_keyboard
            from telecopter.handlers.common import notify_admin_formatted
            admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
            admin_kb = get_admin_request_action_keyboard(request_id)
            await notify_admin_formatted(bot, admin_msg_obj, admin_kb)

    await state.clear()
    from telecopter.handlers.common import _show_main_menu
    await _show_main_menu(message, "✅ Request submitted! What can I help you with next?")


async def my_requests_command_handler(message: Message, bot: Bot, state: FSMContext,
                                      is_triggered_by_command: bool = True):
    if not message.from_user: return

    await _send_my_requests_page_logic(message.from_user.id, 1, message.chat.id, bot,
                                       original_message_id=message.message_id,
                                       is_callback=not is_triggered_by_command,
                                       state=state)


@requests_router.callback_query(F.data.startswith("my_req_page:"))
async def my_requests_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message: return

    try:
        page = int(callback_query.data.split(":")[1])
    except (IndexError, ValueError):
        logger.error("invalid page number in my_requests_callback: %s", callback_query.data)
        if callback_query.message:
            try:
                await callback_query.message.edit_text("❗Error: Could not load that page.", reply_markup=None)
            except Exception as e_edit:
                logger.debug("failed to edit message for page error: %s", e_edit)
                await bot.send_message(callback_query.message.chat.id,
                                       "❗Error: Could not load that page. Please try again.")
        return

    await _send_my_requests_page_logic(callback_query.from_user.id, page, callback_query.message.chat.id, bot,
                                       original_message_id=callback_query.message.message_id,
                                       is_callback=True, state=state)


async def _send_my_requests_page_logic(user_id: int, page: int, chat_id: int, bot: Bot, original_message_id: int,
                                       is_callback: bool, state: FSMContext):
    await state.clear()
    requests_rows = await db.get_user_requests(user_id, page, DEFAULT_PAGE_SIZE)
    total_requests = await db.get_user_requests_count(user_id)
    total_pages = (total_requests + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
    total_pages = max(1, total_pages)

    page_content: List[Union[str, Text, Bold, Italic, Code]] = []
    keyboard_to_show = get_my_requests_pagination_keyboard(page, total_pages)

    if not requests_rows and page == 1:
        page_content.append(Text("🤷 You haven't made any requests or reports yet."))

        builder = InlineKeyboardBuilder()
        builder.button(text="🎬 Request Media", callback_data="main_menu:request_media")
        builder.button(text="⚠️ Report a Problem", callback_data="main_menu:report_problem")
        builder.adjust(1)
        keyboard_to_show = builder.as_markup()

    elif not requests_rows and page > 1:
        page_content.append(Text("✅ No more requests found on this page."))
        builder = InlineKeyboardBuilder.from_markup(
            keyboard_to_show if keyboard_to_show else InlineKeyboardMarkup(inline_keyboard=[]))
        builder.row(InlineKeyboardButton(text="⬅️ Back to Main Menu",
                                         callback_data="main_menu:show_start_menu_from_my_requests"))
        keyboard_to_show = builder.as_markup()

    else:
        page_content.append(Bold(f"📖 Your Requests & Reports (Page {page} of {total_pages})"))
        page_content.append(Text("\n"))

        for req_row in requests_rows:
            req = dict(req_row)
            title_disp = truncate_text(req['title'], 50)
            req_type_icon = "🎬" if req['request_type'] in ["movie", "tv", "manual_media"] else "⚠️"
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

        current_buttons_builder = InlineKeyboardBuilder.from_markup(
            keyboard_to_show if keyboard_to_show else InlineKeyboardMarkup(inline_keyboard=[]))

        has_back_button = False
        if current_buttons_builder._buttons:
            for row_buttons in current_buttons_builder._buttons:
                for button_obj in row_buttons:
                    if hasattr(button_obj,
                               'callback_data') and button_obj.callback_data == "main_menu:show_start_menu_from_my_requests":
                        has_back_button = True
                        break
                if has_back_button:
                    break

        if not has_back_button:
            current_buttons_builder.row(InlineKeyboardButton(text="⬅️ Back to Main Menu",
                                                             callback_data="main_menu:show_start_menu_from_my_requests"))
        keyboard_to_show = current_buttons_builder.as_markup()

    final_text_object = as_list(*page_content, sep="") if page_content else Text("🤷 No requests to display.")
    text_to_send = final_text_object.as_markdown()

    try:
        if is_callback:
            await bot.edit_message_text(
                text=text_to_send,
                chat_id=chat_id,
                message_id=original_message_id,
                reply_markup=keyboard_to_show,
                parse_mode="MarkdownV2"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text_to_send,
                reply_markup=keyboard_to_show,
                parse_mode="MarkdownV2"
            )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug("message not modified for my_requests page %s, user %s: %s", page, user_id, e)
        else:
            logger.error("telegram badrequest in _send_my_requests_page_logic (is_callback=%s, page %s): %s. text: %s",
                         is_callback, page, e, text_to_send[:100])
            if is_callback:
                await bot.send_message(chat_id, "❗Could not update the request list. Please try again.")
    except Exception as e:
        logger.error("exception in _send_my_requests_page_logic (is_callback=%s, page %s): %s", is_callback, page, e)
        if is_callback:
            await bot.send_message(chat_id,
                                   "❗An error occurred updating the request list. Please try again.")
