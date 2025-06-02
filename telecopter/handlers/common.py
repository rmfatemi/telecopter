from typing import Optional, Union

from aiogram import Router, F, Bot
from aiogram.utils.formatting import Text, Bold
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import Message, CallbackQuery, User as AiogramUser, InlineKeyboardMarkup, InlineKeyboardButton

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import ADMIN_GROUP_CHAT_ID

from telecopter.handlers.requests import RequestMediaStates

logger = setup_logger(__name__)

common_router = Router(name="common_router")

MAIN_MENU_KEYBOARD_MARKUP = (
    InlineKeyboardBuilder()
    .add(
        InlineKeyboardButton(text="🎬 Request Media", callback_data="main_menu:request_media"),
        InlineKeyboardButton(text="📊 My Requests", callback_data="main_menu:my_requests"),
        InlineKeyboardButton(text="⚠️ Report a Problem", callback_data="main_menu:report_problem"),
        InlineKeyboardButton(text="❓ Help", callback_data="main_menu:show_help"),
    )
    .adjust(2)
    .as_markup()
)


async def _register_user_if_not_exists(aiogram_user: Optional[AiogramUser], chat_id: int):
    if aiogram_user:
        await db.add_or_update_user(
            user_id=aiogram_user.id, chat_id=chat_id, username=aiogram_user.username, first_name=aiogram_user.first_name
        )
        logger.debug("user %s (chat_id: %s) registration/update processed.", aiogram_user.id, chat_id)
    else:
        logger.warning("could not register user, aiogram user object is none for chat_id %s.", chat_id)


async def _is_admin(user_id: int, bot: Bot) -> bool:
    if not ADMIN_GROUP_CHAT_ID:
        logger.warning("admin_group_chat_id not configured. admin check will always be false.")
        return False
    try:
        member = await bot.get_chat_member(chat_id=ADMIN_GROUP_CHAT_ID, user_id=user_id)
        allowed_statuses = [
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        ]
        if member.status in allowed_statuses:
            logger.debug("user %s is admin in group %s (status: %s)", user_id, ADMIN_GROUP_CHAT_ID, member.status)
            return True
        else:
            logger.debug("user %s is not admin in group %s (status: %s)", user_id, ADMIN_GROUP_CHAT_ID, member.status)
            return False
    except TelegramAPIError as e:
        logger.error(
            "failed to check admin status for user %s in group %s: %s. assuming not admin.",
            user_id,
            ADMIN_GROUP_CHAT_ID,
            e,
        )
        return False
    except Exception as e:
        logger.error(
            "unexpected error checking admin status for user %s in group %s: %s. assuming not admin.",
            user_id,
            ADMIN_GROUP_CHAT_ID,
            e,
        )
        return False


async def notify_admin_formatted(
    bot: Bot, formatted_text_object: Text, keyboard: Optional[InlineKeyboardMarkup] = None
):
    if ADMIN_GROUP_CHAT_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_GROUP_CHAT_ID,
                text=formatted_text_object.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.error("failed to send notification to admin group %s: %s", ADMIN_GROUP_CHAT_ID, e)
    else:
        logger.warning("admin_group_chat_id not configured. cannot send admin notification.")


async def _show_main_menu(message_or_event: Union[Message, CallbackQuery], text: str, parse_mode: Optional[str] = None):
    if isinstance(message_or_event, Message):
        await message_or_event.answer(text, reply_markup=MAIN_MENU_KEYBOARD_MARKUP, parse_mode=parse_mode)
    elif isinstance(message_or_event, CallbackQuery) and message_or_event.message:
        try:
            await message_or_event.message.edit_text(
                text, reply_markup=MAIN_MENU_KEYBOARD_MARKUP, parse_mode=parse_mode
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await message_or_event.answer()
            else:
                await message_or_event.answer("menu already shown or cannot be edited.", show_alert=False)
                if message_or_event.message:
                    await message_or_event.message.answer(
                        text, reply_markup=MAIN_MENU_KEYBOARD_MARKUP, parse_mode=parse_mode
                    )


@common_router.message(CommandStart())
async def start_command_handler(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    if message.from_user:
        await _register_user_if_not_exists(message.from_user, message.chat.id)

        welcome_text_core = (
            f"👋 Hello {message.from_user.first_name}!\n\n"
            "I'm Telecopter, your friendly media request bot. "
            "Use the buttons below to get started."
        )
        if await _is_admin(message.from_user.id, bot):
            welcome_text_core += "\n\n👑 Admin note: New requests will be sent to your admin group."

        await _show_main_menu(message, welcome_text_core)


@common_router.callback_query(F.data == "main_menu:show_help")
async def main_menu_help_callback_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message:
        return
    await help_command_logic(callback_query, state, bot, callback_query.from_user.id)


async def help_command_logic(
    event: Union[Message, CallbackQuery], state: FSMContext, bot: Bot, user_id_for_admin_check: int
):
    await state.clear()
    help_text_content_list = [
        Bold("❓ How to use Telecopter Bot:"),
        Text("\n\nUse the main menu buttons to navigate:\n"),
        Text("\n🎬 "),
        Bold("Request Media:"),
        Text(" Find and request new movies or TV shows."),
        Text("\n📊 "),
        Bold("My Requests:"),
        Text(" Check the status of your past requests."),
        Text("\n⚠️ "),
        Bold("Report a Problem:"),
        Text(" Let us know if something is wrong."),
        Text("\n\nType /start anytime to see the main menu, or /cancel to stop any current action."),
    ]
    if await _is_admin(user_id_for_admin_check, bot):
        help_text_content_list.extend(
            [
                Text("\n\n👑 "),
                Bold("Admin Info:"),
                Text(" You receive new requests and reports with action buttons in your designated admin group. "),
                Text("Future updates might include an admin panel here for easier overview of pending items."),
            ]
        )

    help_text_formatted = Text(*help_text_content_list)
    await _show_main_menu(event, help_text_formatted.as_html(), parse_mode="HTML")


@common_router.message(Command("help"))
async def help_command_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user:
        return
    await help_command_logic(message, state, bot, message.from_user.id)


@common_router.callback_query(F.data == "main_menu:request_media")
async def main_menu_request_media_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if not callback_query.message or not callback_query.from_user:
        return
    await callback_query.answer()
    await _register_user_if_not_exists(callback_query.from_user, callback_query.message.chat.id)

    from telecopter.config import TMDB_API_KEY

    if not TMDB_API_KEY:
        await callback_query.message.answer("⚠️ Media search is currently unavailable. Please try again later.")
        return

    await callback_query.message.answer("✍️ What movie or TV show are you looking for?\nPlease type the name below.")
    await state.set_state(RequestMediaStates.typing_media_name)


@common_router.callback_query(F.data == "main_menu:my_requests")
async def main_menu_my_requests_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if not callback_query.message or not callback_query.from_user:
        return
    await callback_query.answer()
    await _register_user_if_not_exists(callback_query.from_user, callback_query.message.chat.id)
    from telecopter.handlers.requests import my_requests_command_handler as requests_my_requests_logic

    await requests_my_requests_logic(callback_query.message, bot, state, is_triggered_by_command=False)


@common_router.callback_query(F.data == "main_menu:report_problem")
async def main_menu_report_problem_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if not callback_query.message or not callback_query.from_user:
        return
    await callback_query.answer()
    await _register_user_if_not_exists(callback_query.from_user, callback_query.message.chat.id)
    from telecopter.handlers.report import report_command_entry_handler as report_entry_logic

    await report_entry_logic(callback_query.message, state, bot, is_triggered_by_command=False)


@common_router.callback_query(F.data == "main_menu:show_start_menu_from_my_requests")
async def handle_back_to_main_menu_from_my_requests(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    if not callback_query.from_user or not callback_query.message:
        return

    welcome_text_core = (
        f"👋 Hello {callback_query.from_user.first_name}!\n\nWelcome back to the main menu. What would you like to do?"
    )

    await _show_main_menu(callback_query, welcome_text_core)


@common_router.message(Command("cancel"), StateFilter("*"))
@common_router.callback_query(F.data.in_({"action_cancel", "main_menu:cancel_current_action"}), StateFilter("*"))
async def universal_cancel_handler(event: Union[Message, CallbackQuery], state: FSMContext):
    user_id = event.from_user.id if event.from_user else "unknown"
    current_state_str = await state.get_state()

    action_cancelled_text = "✅ Action cancelled. What can I help you with next?"

    if current_state_str is not None:
        logger.info("user %s cancelled conversation from state %s.", user_id, current_state_str)
        await state.clear()
        if isinstance(event, Message):
            await _show_main_menu(event, action_cancelled_text)
        elif isinstance(event, CallbackQuery) and event.message:
            await event.answer("Action cancelled.", show_alert=False)
            await _show_main_menu(event, action_cancelled_text)
    else:
        logger.info("user %s used cancel outside of a conversation.", user_id)
        no_active_action_text = "🤷 No active operation to cancel. Here's the main menu:"
        if isinstance(event, Message):
            await _show_main_menu(event, no_active_action_text)
        elif isinstance(event, CallbackQuery):
            await event.answer("No active operation.", show_alert=False)
            if event.message:
                await _show_main_menu(event, no_active_action_text)


@common_router.message(StateFilter(None), F.text)
async def unhandled_text_message_handler(message: Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        logger.info(
            "unhandled command from user %s: %s", message.from_user.id if message.from_user else "unknown", message.text
        )
        return

    logger.info(
        "unhandled text message from user %s: %s",
        message.from_user.id if message.from_user else "unknown",
        message.text[:50],
    )
    first_name = message.from_user.first_name if message.from_user else "there"
    response_text = (
        f"🤔 Hmm, I didn't quite get that, {first_name}.\n"
        "Please use the buttons below, or type /start to see what I can do!"
    )
    await _show_main_menu(message, response_text)


@common_router.message(StateFilter(None))
async def unhandled_non_text_message_handler(message: Message, state: FSMContext):
    logger.info(
        "unhandled non-text message (type: %s) from user %s",
        message.content_type,
        message.from_user.id if message.from_user else "unknown",
    )
    first_name = message.from_user.first_name if message.from_user else "there"
    response_text = (
        f"😕 Sorry {first_name}, I can only understand text messages and button presses for now.\n"
        "Please use the buttons below, or type /start to see what I can do!"
    )
    await _show_main_menu(message, response_text)
