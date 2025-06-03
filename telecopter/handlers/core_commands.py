from typing import Union

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import Text, Bold
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder

from telecopter.logger import setup_logger
from telecopter.handlers.common_utils import (
    register_user_if_not_exists,
    is_admin,
    notify_admin_formatted,
    format_user_for_admin_notification,
    ensure_user_approved,
)
import telecopter.database as db
from telecopter.constants import (
    USER_STATUS_NEW,
    USER_STATUS_PENDING_APPROVAL,
    USER_STATUS_APPROVED,
    USER_STATUS_REJECTED,
    REQUEST_TYPE_USER_APPROVAL,
    CALLBACK_USER_ACCESS_REQUEST_PREFIX,
    CALLBACK_USER_ACCESS_REQUEST_ACTION,
    CALLBACK_USER_ACCESS_LATER_ACTION,
    CALLBACK_USER_APPROVAL_TASK_ACTION_PREFIX,
    CALLBACK_USER_APPROVAL_TASK_APPROVE,
    CALLBACK_USER_APPROVAL_TASK_REJECT,
    MSG_START_WELCOME_NEW_PROMPT,
    MSG_START_PENDING_APPROVAL,
    MSG_START_REJECTED,
    MSG_START_UNEXPECTED_STATUS_ERROR,
    MSG_USER_ACCESS_REQUEST_SUBMITTED,
    MSG_USER_ACCESS_REQUEST_SUBMITTED_ALERT,
    MSG_USER_ACCESS_DEFERRED,
    MSG_USER_ACCESS_DEFERRED_ALERT,
    BTN_REQUEST_ACCESS,
    BTN_MAYBE_LATER,
    MSG_ADMIN_NOTIFY_NEW_USER_TASK_TITLE,
    MSG_ADMIN_NOTIFY_USER_LABEL,
    MSG_ADMIN_NOTIFY_USER_ID_LABEL,
    MSG_ADMIN_NOTIFY_TASK_ID_LABEL,
    MSG_ADMIN_NOTIFY_PLEA,
    BTN_APPROVE_USER_ACTION,
    BTN_REJECT_USER_ACTION,
    MSG_ACTION_CANCELLED_MENU,
    MSG_NO_ACTIVE_OPERATION_MENU,
    MSG_NO_ACTIVE_OPERATION_ALERT,
    MSG_ACTION_CANCELLED_ALERT,
    MSG_HELP_TITLE,
    MSG_HELP_NAVIGATION,
    MSG_HELP_REQUEST_MEDIA_ICON,
    MSG_HELP_REQUEST_MEDIA_TITLE,
    MSG_HELP_REQUEST_MEDIA_DESC,
    MSG_HELP_MY_REQUESTS_ICON,
    MSG_HELP_MY_REQUESTS_TITLE,
    MSG_HELP_MY_REQUESTS_DESC,
    MSG_HELP_REPORT_PROBLEM_ICON,
    MSG_HELP_REPORT_PROBLEM_TITLE,
    MSG_HELP_REPORT_PROBLEM_DESC,
    MSG_HELP_START_ANYTIME,
    MSG_HELP_CANCEL_ACTION,
    MSG_HELP_ADMIN_INFO_ICON,
    MSG_HELP_ADMIN_INFO_TITLE,
    MSG_HELP_ADMIN_INFO_DESC,
    MSG_ERROR_PROCESSING_ACTION_ALERT,
    MSG_ADMIN_UNKNOWN_ACTION_ALERT,
    CALLBACK_ACTION_CANCEL,
    CALLBACK_MAIN_MENU_CANCEL_ACTION,
)

logger = setup_logger(__name__)

core_commands_router = Router(name="core_commands_router")


def get_request_access_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_REQUEST_ACCESS,
        callback_data=f"{CALLBACK_USER_ACCESS_REQUEST_PREFIX}:{CALLBACK_USER_ACCESS_REQUEST_ACTION}",
    )
    builder.button(
        text=BTN_MAYBE_LATER, callback_data=f"{CALLBACK_USER_ACCESS_REQUEST_PREFIX}:{CALLBACK_USER_ACCESS_LATER_ACTION}"
    )
    builder.adjust(1)
    return builder


@core_commands_router.message(CommandStart())
async def start_command_handler(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    if not message.from_user:
        return

    await register_user_if_not_exists(message.from_user, message.chat.id, bot)
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    approval_status = await db.get_user_approval_status(user_id)
    is_bot_admin = await is_admin(user_id, bot)

    if is_bot_admin:
        from telecopter.handlers.admin_panel import show_admin_panel

        await show_admin_panel(message, bot)
        return

    if approval_status == USER_STATUS_APPROVED:
        from telecopter.handlers.main_menu import show_main_menu_for_user

        await show_main_menu_for_user(message, bot)
    elif approval_status == USER_STATUS_PENDING_APPROVAL:
        await message.answer(MSG_START_PENDING_APPROVAL.format(user_name=user_name))
    elif approval_status == USER_STATUS_REJECTED:
        await message.answer(MSG_START_REJECTED.format(user_name=user_name))
    elif approval_status == USER_STATUS_NEW:
        keyboard = get_request_access_keyboard()
        await message.answer(
            MSG_START_WELCOME_NEW_PROMPT.format(user_name=user_name), reply_markup=keyboard.as_markup()
        )
    else:
        logger.error("user %s has an unexpected approval status: %s", user_id, approval_status)
        await message.answer(MSG_START_UNEXPECTED_STATUS_ERROR)


@core_commands_router.callback_query(F.data.startswith(f"{CALLBACK_USER_ACCESS_REQUEST_PREFIX}:"))
async def handle_user_access_request_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    if not callback_query.from_user or not callback_query.message:
        await callback_query.answer(MSG_ERROR_PROCESSING_ACTION_ALERT, show_alert=True)
        return

    action = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    user_name = callback_query.from_user.full_name

    if action == CALLBACK_USER_ACCESS_REQUEST_ACTION:
        await db.update_user_approval_status(user_id, USER_STATUS_PENDING_APPROVAL)

        task_title = f"User Approval: {user_name} ({user_id})"
        task_id = await db.add_request(
            user_id=user_id, request_type=REQUEST_TYPE_USER_APPROVAL, title=task_title, status="pending_admin"
        )
        logger.info("created user_approval task (id: %s) for user %s", task_id, user_id)

        await callback_query.message.edit_text(MSG_USER_ACCESS_REQUEST_SUBMITTED, reply_markup=None)
        await callback_query.answer(MSG_USER_ACCESS_REQUEST_SUBMITTED_ALERT)

        user_details_formatted_text = await format_user_for_admin_notification(user_id, bot)
        admin_notify_text_obj = Text(
            Bold(MSG_ADMIN_NOTIFY_NEW_USER_TASK_TITLE),
            "\n\n",
            MSG_ADMIN_NOTIFY_USER_LABEL,
            user_details_formatted_text,
            MSG_ADMIN_NOTIFY_USER_ID_LABEL.format(user_id=user_id),
            MSG_ADMIN_NOTIFY_TASK_ID_LABEL.format(task_id=task_id),
            MSG_ADMIN_NOTIFY_PLEA,
        )
        admin_keyboard = InlineKeyboardBuilder()
        admin_keyboard.button(
            text=BTN_APPROVE_USER_ACTION,
            callback_data=(
                f"{CALLBACK_USER_APPROVAL_TASK_ACTION_PREFIX}:{CALLBACK_USER_APPROVAL_TASK_APPROVE}:{user_id}:{task_id}"
            ),
        )
        admin_keyboard.button(
            text=BTN_REJECT_USER_ACTION,
            callback_data=(
                f"{CALLBACK_USER_APPROVAL_TASK_ACTION_PREFIX}:{CALLBACK_USER_APPROVAL_TASK_REJECT}:{user_id}:{task_id}"
            ),
        )
        admin_keyboard.adjust(1)
        await notify_admin_formatted(bot, admin_notify_text_obj, admin_keyboard.as_markup())

    elif action == CALLBACK_USER_ACCESS_LATER_ACTION:
        await callback_query.message.edit_text(MSG_USER_ACCESS_DEFERRED, reply_markup=None)
        await callback_query.answer(MSG_USER_ACCESS_DEFERRED_ALERT)
    else:
        await callback_query.answer(MSG_ADMIN_UNKNOWN_ACTION_ALERT, show_alert=True)
        logger.warning("unknown user access request action: %s for user %s", action, user_id)


async def help_command_logic(
    event: Union[Message, CallbackQuery], state: FSMContext, bot: Bot, user_id_for_admin_check: int
):
    from telecopter.handlers.main_menu import show_main_menu_for_user

    if not await ensure_user_approved(event, bot, state):
        return

    await state.clear()
    help_text_content_list = [
        Bold(MSG_HELP_TITLE),
        Text(MSG_HELP_NAVIGATION),
        Text(MSG_HELP_REQUEST_MEDIA_ICON),
        Bold(MSG_HELP_REQUEST_MEDIA_TITLE),
        Text(MSG_HELP_REQUEST_MEDIA_DESC),
        Text(MSG_HELP_MY_REQUESTS_ICON),
        Bold(MSG_HELP_MY_REQUESTS_TITLE),
        Text(MSG_HELP_MY_REQUESTS_DESC),
        Text(MSG_HELP_REPORT_PROBLEM_ICON),
        Bold(MSG_HELP_REPORT_PROBLEM_TITLE),
        Text(MSG_HELP_REPORT_PROBLEM_DESC),
        Text(MSG_HELP_START_ANYTIME),
        Text(MSG_HELP_CANCEL_ACTION),
    ]
    if await is_admin(user_id_for_admin_check, bot):
        help_text_content_list.extend(
            [Text(MSG_HELP_ADMIN_INFO_ICON), Bold(MSG_HELP_ADMIN_INFO_TITLE), Text(MSG_HELP_ADMIN_INFO_DESC)]
        )

    help_text_formatted = Text(*help_text_content_list)
    await show_main_menu_for_user(event, bot, custom_text_html=help_text_formatted.as_html())


@core_commands_router.message(Command("cancel"), StateFilter("*"))
@core_commands_router.callback_query(
    F.data.in_({CALLBACK_ACTION_CANCEL, CALLBACK_MAIN_MENU_CANCEL_ACTION}), StateFilter("*")
)
async def universal_cancel_handler(event: Union[Message, CallbackQuery], state: FSMContext, bot: Bot):
    from telecopter.handlers.main_menu import show_main_menu_for_user

    user_id = event.from_user.id if event.from_user else "unknown"
    current_state_str = await state.get_state()

    if current_state_str is not None:
        logger.info("user %s cancelled conversation from state %s.", user_id, current_state_str)
        await state.clear()
        if isinstance(event, CallbackQuery) and event.message:
            await event.answer(MSG_ACTION_CANCELLED_ALERT, show_alert=False)
        await show_main_menu_for_user(event, bot, custom_text_str=MSG_ACTION_CANCELLED_MENU)
    else:
        logger.info("user %s used cancel outside of a conversation.", user_id)
        if isinstance(event, CallbackQuery):
            await event.answer(MSG_NO_ACTIVE_OPERATION_ALERT, show_alert=False)
        await show_main_menu_for_user(event, bot, custom_text_str=MSG_NO_ACTIVE_OPERATION_MENU)
