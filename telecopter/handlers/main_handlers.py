from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.formatting import Text

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.utils import format_request_for_admin
from telecopter.handlers.menu_utils import show_main_menu_for_user, show_admin_panel
# --- Start of Correction ---
from telecopter.handlers.common_utils import ensure_user_approved, notify_admin_formatted, is_admin
# --- End of Correction ---
from telecopter.handlers.request_handlers import my_requests_entrypoint
from telecopter.handlers.admin_handlers import get_admin_report_action_keyboard
from telecopter.handlers.handler_states import RequestMediaStates, ReportProblemStates
from telecopter.constants import (
    MSG_USER_ACCESS_REQUEST_SUBMITTED,
    MSG_USER_ACCESS_PENDING_INFO,
    MSG_START_REJECTED,
    MSG_ACTION_CANCELLED_MENU,
    MSG_NO_ACTIVE_OPERATION_MENU,
    MSG_FALLBACK_UNHANDLED_TEXT,
    MainMenuCallback,
    GenericCallbackAction,
    PROMPT_PROBLEM_DESCRIPTION,
    MSG_REPORT_SUBMITTED,
    MSG_REPORT_SUCCESS,
    ERR_PROBLEM_DESCRIPTION_TOO_SHORT,
    PROMPT_MEDIA_NAME_TYPING,
    RequestType,
)

logger = setup_logger(__name__)

main_router = Router(name="main_router")


@main_router.message(Command("start"))
async def start_command(message: Message, bot: Bot, state: FSMContext):
    if not message.from_user:
        return
    await state.clear()

    user_id = message.from_user.id
    
    # --- Start of Correction ---
    if await is_admin(user_id):
        await show_admin_panel(message, bot)
        return
    # --- End of Correction ---

    user_details_from_tg = message.from_user
    chat_id = message.chat.id

    user_in_db_row = await db.get_user(user_id)
    if user_in_db_row:
        user_in_db = dict(user_in_db_row)
        if user_in_db["approval_status"] == "approved":
            await show_main_menu_for_user(message, bot)
        elif user_in_db["approval_status"] == "pending_approval":
            reply_text_obj = Text(MSG_USER_ACCESS_PENDING_INFO)
            await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        else:
            user_name = user_in_db.get("first_name", "there")
            reply_text_obj = Text(MSG_START_REJECTED.format(user_name=user_name))
            await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
    else:
        await db.add_or_update_user(
            user_id=user_id,
            chat_id=chat_id,
            username=user_details_from_tg.username,
            first_name=user_details_from_tg.first_name,
        )
        reply_text_obj = Text(MSG_USER_ACCESS_REQUEST_SUBMITTED)
        await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        await notify_admin_formatted(bot, f"New user waiting for approval: {user_id}", None)


@main_router.message(Command("admin"))
async def admin_command(message: Message, bot: Bot):
    if not message.from_user:
        return
    await show_admin_panel(message, bot)


@main_router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    if current_state is None:
        reply_text_obj = Text(MSG_NO_ACTIVE_OPERATION_MENU)
        await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    logger.info("user %s cancelled state %s", message.from_user.id, current_state)
    await state.clear()
    reply_text_obj = Text(MSG_ACTION_CANCELLED_MENU)
    await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
    await show_main_menu_for_user(message, bot)


@main_router.callback_query(F.data == GenericCallbackAction.CANCEL.value)
async def cancel_callback_handler(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    await callback_query.answer()
    current_state = await state.get_state()
    if not current_state:
        if callback_query.message:
            try:
                await callback_query.message.delete()
            except Exception:
                pass
        await show_main_menu_for_user(callback_query, bot)
        return

    await state.clear()
    if callback_query.message:
        try:
            await callback_query.message.delete()
        except Exception:
            pass
    await show_main_menu_for_user(
        callback_query, bot, custom_text_str=MSG_ACTION_CANCELLED_MENU
    )


@main_router.callback_query(F.data.startswith("main_menu:"))
async def main_menu_cb_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if not await ensure_user_approved(callback_query, bot, state):
        return

    action = callback_query.data.split(":")[1]
    await callback_query.answer()

    if callback_query.message is None or callback_query.from_user is None:
        return

    if action == MainMenuCallback.REQUEST_MEDIA.value:
        await state.set_state(RequestMediaStates.typing_media_name)
        text_obj = Text(PROMPT_MEDIA_NAME_TYPING)
        await callback_query.message.edit_text(text_obj.as_markdown(), parse_mode="MarkdownV2")

    elif action == MainMenuCallback.MY_REQUESTS.value:
        await my_requests_entrypoint(
            base_message=callback_query.message,
            requesting_user_id=callback_query.from_user.id,
            bot=bot,
            state=state,
            is_callback=True,
        )

    elif action == MainMenuCallback.REPORT_PROBLEM.value:
        await state.set_state(ReportProblemStates.typing_problem)
        text_obj = Text(PROMPT_PROBLEM_DESCRIPTION)
        await callback_query.message.edit_text(text_obj.as_markdown(), parse_mode="MarkdownV2")

    elif action == MainMenuCallback.SHOW_START_MENU_FROM_MY_REQUESTS.value:
        await show_main_menu_for_user(callback_query, bot)


# --- Problem Report Logic ---

@main_router.message(StateFilter(ReportProblemStates.typing_problem), F.text)
async def problem_report_description_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user or not message.text:
        return

    problem_description = message.text.strip()
    if len(problem_description) < 10:
        reply_text_obj = Text(ERR_PROBLEM_DESCRIPTION_TOO_SHORT)
        await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        return

    request_id = await db.add_problem_report(message.from_user.id, problem_description)
    reply_text_obj = Text(MSG_REPORT_SUBMITTED)
    await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(message.from_user.id)
    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(
            dict(db_request_row), dict(db_user_row), request_type_override=RequestType.PROBLEM
        )
        admin_kb = get_admin_report_action_keyboard(request_id)
        await notify_admin_formatted(bot, admin_msg_obj, admin_kb)

    await state.clear()
    await show_main_menu_for_user(message, bot, custom_text_str=MSG_REPORT_SUCCESS)


@main_router.message()
async def fallback_handler(message: Message, bot: Bot, state: FSMContext):
    if not message.text or not message.from_user:
        return
    logger.info("fallback handler triggered for user %s with text: %s", message.from_user.id, message.text)

    first_name = message.from_user.first_name
    reply_text_obj = Text(MSG_FALLBACK_UNHANDLED_TEXT.format(first_name=first_name))
    await message.reply(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
    await show_main_menu_for_user(message, bot)
