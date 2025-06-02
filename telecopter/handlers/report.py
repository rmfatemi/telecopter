from aiogram.types import Message, User as AiogramUser
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import MAX_REPORT_LENGTH
from telecopter.utils import truncate_text, format_request_for_admin

logger = setup_logger(__name__)
report_problem_router = Router(name="report_problem_router")


class ReportProblemStates(StatesGroup):
    typing_problem = State()


async def _submit_problem_report_logic(message: Message, problem_text: str, state: FSMContext, bot_instance: Bot):
    if not message.from_user:
        await state.clear()
        return

    problem_text_truncated = truncate_text(problem_text, MAX_REPORT_LENGTH)
    request_id = await db.add_problem_report(message.from_user.id, problem_text_truncated)

    await message.answer("✅ Your problem report has been submitted. Thank you!")
    logger.info("user %s submitted problem report id %s: %s", message.from_user.id, request_id,
                problem_text_truncated[:50])

    db_request_row = await db.get_request_by_id(request_id)
    db_user_row = await db.get_user(message.from_user.id)

    if db_request_row and db_user_row:
        from telecopter.handlers.admin import get_admin_report_action_keyboard
        from telecopter.handlers.common import notify_admin_formatted
        admin_msg_obj = format_request_for_admin(dict(db_request_row), dict(db_user_row))
        admin_keyboard = get_admin_report_action_keyboard(request_id)
        await notify_admin_formatted(bot_instance, admin_msg_obj, admin_keyboard)

    await state.clear()
    from telecopter.handlers.common import _show_main_menu
    await _show_main_menu(message, "✅ Report submitted! What can I help you with next?")


async def report_command_entry_handler(message: Message, state: FSMContext, bot: Bot,
                                       is_triggered_by_command: bool = True):
    if not message.from_user: return

    await message.answer(
        "📝 Please describe the problem you are experiencing below, or use /cancel."
    )
    await state.set_state(ReportProblemStates.typing_problem)


@report_problem_router.message(StateFilter(ReportProblemStates.typing_problem), F.text)
async def problem_report_text_handler(message: Message, state: FSMContext, bot: Bot):
    if not message.text or not message.from_user:
        await message.answer("✍️ Please type your problem description, or use /cancel.")
        await state.set_state(ReportProblemStates.typing_problem)
        return

    problem_description = message.text.strip()
    if len(problem_description) < 10:
        await message.answer(
            "✍️ Your description seems a bit short. Please provide more details to help us understand the issue, or use /cancel.")
        await state.set_state(ReportProblemStates.typing_problem)
        return

    await _submit_problem_report_logic(message, problem_description, state, bot)
