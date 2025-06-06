from typing import Union

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import Text, Bold
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command, CommandStart, StateFilter

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.handlers.common_utils import (
    format_user_for_admin_notification,
    register_user_if_not_exists,
    notify_admin_formatted,
    IsAdminFilter,
    is_admin,
)
from telecopter.handlers.menu_utils import show_admin_panel, show_main_menu_for_user
from telecopter.constants import (
    USER_STATUS_NEW,
    USER_STATUS_PENDING_APPROVAL,
    USER_STATUS_APPROVED,
    USER_STATUS_REJECTED,
    CALLBACK_USER_ACCESS_REQUEST_PREFIX,
    CALLBACK_USER_ACCESS_REQUEST_ACTION,
    CALLBACK_USER_ACCESS_LATER_ACTION,
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
    MSG_ADMIN_NOTIFY_NEW_USER,
    MSG_ADMIN_NOTIFY_USER_LABEL,
    MSG_ADMIN_NOTIFY_PLEA,
    BTN_APPROVE_USER,
    BTN_REJECT_USER,
    MSG_ACTION_CANCELLED_MENU,
    MSG_NO_ACTIVE_OPERATION_MENU,
    MSG_NO_ACTIVE_OPERATION_ALERT,
    MSG_ACTION_CANCELLED_ALERT,
    MSG_ERROR_PROCESSING_ACTION_ALERT,
    MSG_ADMIN_UNKNOWN_ACTION_ALERT,
    CALLBACK_ACTION_CANCEL,
    CALLBACK_MAIN_MENU_CANCEL_ACTION,
    CALLBACK_MANAGE_USERS_PREFIX,
    CALLBACK_MANAGE_USERS_APPROVE,
    CALLBACK_MANAGE_USERS_REJECT,
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


@core_commands_router.message(CommandStart(), IsAdminFilter())
async def start_admin(message: Message, bot: Bot):
    logger.info(f"admin user {message.from_user.id} initiated /start.")
    await show_admin_panel(message, bot)


@core_commands_router.message(CommandStart())
async def start_user(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    if not message.from_user:
        return

    await register_user_if_not_exists(message.from_user, message.chat.id, bot)
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    approval_status = await db.get_user_approval_status(user_id)

    if approval_status == USER_STATUS_APPROVED:
        await show_main_menu_for_user(message, bot)
    elif approval_status == USER_STATUS_PENDING_APPROVAL:
        text_obj = Text(MSG_START_PENDING_APPROVAL.format(user_name=user_name))
        await message.answer(text_obj.as_markdown(), parse_mode="MarkdownV2")
    elif approval_status == USER_STATUS_REJECTED:
        text_obj = Text(MSG_START_REJECTED.format(user_name=user_name))
        await message.answer(text_obj.as_markdown(), parse_mode="MarkdownV2")
    elif approval_status == USER_STATUS_NEW:
        keyboard = get_request_access_keyboard()
        text_obj = Text(MSG_START_WELCOME_NEW_PROMPT.format(user_name=user_name))
        await message.answer(text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=keyboard.as_markup())
    else:
        logger.error("user %s has an unexpected approval status: %s", user_id, approval_status)
        text_obj = Text(MSG_START_UNEXPECTED_STATUS_ERROR)
        await message.answer(text_obj.as_markdown(), parse_mode="MarkdownV2")


@core_commands_router.callback_query(F.data.startswith(f"{CALLBACK_USER_ACCESS_REQUEST_PREFIX}:"))
async def handle_user_access_request_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    if not callback_query.from_user or not callback_query.message:
        await callback_query.answer(MSG_ERROR_PROCESSING_ACTION_ALERT, show_alert=True)
        return

    action = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id

    if action == CALLBACK_USER_ACCESS_REQUEST_ACTION:
        await db.update_user_approval_status(user_id, USER_STATUS_PENDING_APPROVAL)
        logger.info("user %s requested access, status set to pending_approval.", user_id)

        text_obj = Text(MSG_USER_ACCESS_REQUEST_SUBMITTED)
        await callback_query.message.edit_text(text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None)
        await callback_query.answer(MSG_USER_ACCESS_REQUEST_SUBMITTED_ALERT)

        user_details_formatted_text = await format_user_for_admin_notification(user_id, bot)
        admin_notify_text_obj = Text(
            Bold(MSG_ADMIN_NOTIFY_NEW_USER),
            "\n\n",
            MSG_ADMIN_NOTIFY_USER_LABEL,
            user_details_formatted_text,
            MSG_ADMIN_NOTIFY_PLEA,
        )
        admin_keyboard = InlineKeyboardBuilder()
        admin_keyboard.button(
            text=BTN_APPROVE_USER,
            callback_data=f"{CALLBACK_MANAGE_USERS_PREFIX}:{CALLBACK_MANAGE_USERS_APPROVE}:{user_id}",
        )
        admin_keyboard.button(
            text=BTN_REJECT_USER,
            callback_data=f"{CALLBACK_MANAGE_USERS_PREFIX}:{CALLBACK_MANAGE_USERS_REJECT}:{user_id}",
        )
        admin_keyboard.adjust(1)
        await notify_admin_formatted(bot, admin_notify_text_obj, admin_keyboard.as_markup())

    elif action == CALLBACK_USER_ACCESS_LATER_ACTION:
        text_obj = Text(MSG_USER_ACCESS_DEFERRED)
        await callback_query.message.edit_text(text_obj.as_markdown(), parse_mode="MarkdownV2", reply_markup=None)
        await callback_query.answer(MSG_USER_ACCESS_DEFERRED_ALERT)
    else:
        await callback_query.answer(MSG_ADMIN_UNKNOWN_ACTION_ALERT, show_alert=True)
        logger.warning("unknown user access request action: %s for user %s", action, user_id)


@core_commands_router.message(Command("cancel"), StateFilter("*"))
@core_commands_router.callback_query(
    F.data.in_({CALLBACK_ACTION_CANCEL, CALLBACK_MAIN_MENU_CANCEL_ACTION}), StateFilter("*")
)
async def universal_cancel_handler(event: Union[Message, CallbackQuery], state: FSMContext, bot: Bot):
    user = event.from_user
    if not user:
        return

    is_in_state = await state.get_state() is not None

    if is_in_state:
        logger.info("user %s cancelled conversation.", user.id)
        await state.clear()
        if isinstance(event, CallbackQuery):
            await event.answer(MSG_ACTION_CANCELLED_ALERT, show_alert=False)
    else:
        logger.info("user %s used cancel outside of a conversation.", user.id)
        if isinstance(event, CallbackQuery):
            await event.answer(MSG_NO_ACTIVE_OPERATION_ALERT, show_alert=False)

    if await is_admin(user.id):
        await show_admin_panel(event, bot)
    else:
        message_text = MSG_ACTION_CANCELLED_MENU if is_in_state else MSG_NO_ACTIVE_OPERATION_MENU
        text_obj = Text(message_text)
        await show_main_menu_for_user(event, bot, custom_text_obj=text_obj)
