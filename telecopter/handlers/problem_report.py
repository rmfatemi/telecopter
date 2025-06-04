from aiogram.types import Message
from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.utils.formatting import Text
from aiogram.fsm.context import FSMContext

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import MAX_REPORT_LENGTH
from telecopter.handlers.handler_states import ReportProblemStates
from telecopter.handlers.common_utils import notify_admin_formatted
from telecopter.utils import truncate_text, format_request_for_admin
from telecopter.handlers.admin_moderate import get_admin_report_action_keyboard
from telecopter.constants import (
    MSG_REPORT_SUBMITTED,
    MSG_REPORT_SUCCESS,
    PROMPT_PROBLEM_DESCRIPTION,
    PROMPT_PROBLEM_DESCRIPTION_RETRY,
    ERR_PROBLEM_DESCRIPTION_TOO_SHORT,
)

logger = setup_logger(__name__)

problem_report_router = Router(name="problem_report_router")


async def _submit_problem_report_logic(message: Message, problem_text: str, state: FSMContext, bot_instance: Bot):
    from .main_menu import show_main_menu_for_user

    if not message.from_user:
        await state.clear()
        return

    problem_text_truncated = truncate_text(problem_text, MAX_REPORT_LENGTH)
    request_id = await db.add_problem_report(message.from_user.id, problem_text_truncated)

    reply_text_obj = Text(MSG_REPORT_SUBMITTED)
    await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
    logger.info(
        "user %s submitted problem report id %s: %s", message.from_user.id, request_id, problem_text_truncated[:50]
    )

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(message.from_user.id)

    if db_request_row and db_user_row:
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_keyboard = get_admin_report_action_keyboard(request_id)
        await notify_admin_formatted(bot_instance, admin_msg_obj, admin_keyboard)

    await state.clear()
    await show_main_menu_for_user(message, bot_instance, custom_text_str=MSG_REPORT_SUCCESS)


async def report_command_entry_handler(
    message: Message, state: FSMContext, bot: Bot, is_triggered_by_command: bool = True
):
    if not message.from_user:
        return
    prompt_text_obj = Text(PROMPT_PROBLEM_DESCRIPTION)
    await message.answer(prompt_text_obj.as_markdown(), parse_mode="MarkdownV2")
    await state.set_state(ReportProblemStates.typing_problem)


@problem_report_router.message(StateFilter(ReportProblemStates.typing_problem), F.text)
async def problem_report_text_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.text or not message.from_user:
        reply_text_obj = Text(PROMPT_PROBLEM_DESCRIPTION_RETRY)
        await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        await state.set_state(ReportProblemStates.typing_problem)
        return

    problem_description = message.text.strip()
    if len(problem_description) < 10:
        reply_text_obj = Text(ERR_PROBLEM_DESCRIPTION_TOO_SHORT)
        await message.answer(reply_text_obj.as_markdown(), parse_mode="MarkdownV2")
        await state.set_state(ReportProblemStates.typing_problem)
        return
    await _submit_problem_report_logic(message, problem_description, state, bot)
