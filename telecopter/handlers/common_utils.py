import asyncio

from typing import Optional, Union

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import Text, TextLink
from aiogram.exceptions import TelegramAPIError
from aiogram.types import User as AiogramUser, InlineKeyboardMarkup, Message, CallbackQuery

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import ADMIN_CHAT_IDS
from telecopter.constants import (
    USER_STATUS_APPROVED,
    USER_STATUS_PENDING_APPROVAL,
    USER_STATUS_REJECTED,
    USER_STATUS_NEW,
    MSG_USER_ACCESS_PENDING_INFO,
    MSG_USER_REJECTED_INFO,
    MSG_USER_NEW_INFO_START_REQUIRED,
    MSG_USER_UNKNOWN_STATUS_INFO,
)


logger = setup_logger(__name__)


async def register_user_if_not_exists(aiogram_user: Optional[AiogramUser], chat_id: int, bot: Bot):
    if aiogram_user:
        is_bot_admin_flag = await is_admin(aiogram_user.id)
        await db.add_or_update_user(
            user_id=aiogram_user.id,
            chat_id=chat_id,
            username=aiogram_user.username,
            first_name=aiogram_user.first_name,
            is_admin_user=is_bot_admin_flag,
        )
        logger.debug("user %s (chat_id: %s) registration/update processed.", aiogram_user.id, chat_id)
    else:
        logger.warning("could not register user, aiogram user object is none for chat_id %s.", chat_id)


async def is_admin(user_id: int) -> bool:
    if not ADMIN_CHAT_IDS:
        logger.debug("ADMIN_CHAT_IDS not configured. User %s considered not admin.", user_id)
        return False

    is_user_admin = user_id in ADMIN_CHAT_IDS
    if is_user_admin:
        logger.debug("User %s is in ADMIN_CHAT_IDS and considered admin.", user_id)
    else:
        logger.debug("User %s is NOT in ADMIN_CHAT_IDS and considered not admin.", user_id)
    return is_user_admin


async def notify_admin_formatted(
    bot: Bot, formatted_text_object: Text, keyboard: Optional[InlineKeyboardMarkup] = None
):
    if not ADMIN_CHAT_IDS:
        logger.warning("ADMIN_CHAT_IDS not configured. Cannot send admin notification.")
        return

    success_count = 0
    failure_count = 0
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=formatted_text_object.as_markdown(),
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
            logger.info("Sent notification to admin_id %s.", admin_id)
            success_count += 1
        except TelegramAPIError as e:
            logger.error("Failed to send notification to admin_id %s: %s", admin_id, e)
            failure_count += 1
        except Exception as e:
            logger.error("Unexpected error sending notification to admin_id %s: %s", admin_id, e)
            failure_count += 1
        if len(ADMIN_CHAT_IDS) > 1:
            await asyncio.sleep(0.1)

    if failure_count > 0:
        logger.warning(f"Admin notifications: {success_count} sent, {failure_count} failed.")


async def ensure_user_approved(event: Union[Message, CallbackQuery], bot: Bot, state: FSMContext) -> bool:
    if not event.from_user:
        return False

    is_bot_admin_flag = await is_admin(event.from_user.id)
    if is_bot_admin_flag:
        return True

    user_status = await db.get_user_approval_status(event.from_user.id)

    message_text = ""
    show_alert_flag = isinstance(event, CallbackQuery)
    user_can_proceed = False

    if user_status == USER_STATUS_APPROVED:
        user_can_proceed = True
    elif user_status == USER_STATUS_PENDING_APPROVAL:
        message_text = MSG_USER_ACCESS_PENDING_INFO
    elif user_status == USER_STATUS_REJECTED:
        message_text = MSG_USER_REJECTED_INFO
    elif user_status == USER_STATUS_NEW:
        message_text = MSG_USER_NEW_INFO_START_REQUIRED
    else:
        message_text = MSG_USER_UNKNOWN_STATUS_INFO
        logger.warning("user %s has an unknown approval status: %s", event.from_user.id, user_status)

    if not user_can_proceed:
        current_fsm_state = await state.get_state()
        if current_fsm_state is not None:
            await state.clear()
            logger.info(
                "cleared state for user %s due to non-approved access attempt from state %s.",
                event.from_user.id,
                current_fsm_state,
            )

        if isinstance(event, Message):
            text_obj = Text(message_text)
            await event.answer(text_obj.as_markdown(), parse_mode="MarkdownV2")
        elif isinstance(event, CallbackQuery):
            await event.answer(message_text, show_alert=show_alert_flag)
            if event.message:
                try:
                    await event.message.edit_reply_markup(reply_markup=None)
                except Exception as e:
                    logger.debug("could not edit reply markup in ensure_user_approved: %s", e)
    return user_can_proceed


async def format_user_for_admin_notification(user_id: int, bot: Bot) -> Text:
    user_db_info = await db.get_user(user_id)
    name_to_display = f"user id {user_id}"
    username_to_display = None

    if user_db_info:
        try:
            name_to_display = user_db_info["first_name"] or str(user_id)
        except KeyError:
            name_to_display = str(user_id)
            logger.warning("first_name key missing in user_db_info for user_id: %s", user_id)

        try:
            username_to_display = user_db_info["username"]
        except KeyError:
            username_to_display = None
            logger.debug("username key missing or None in user_db_info for user_id: %s", user_id)

        try:
            user_tg_info = await bot.get_chat(user_id)
            if user_tg_info:
                name_to_display = user_tg_info.full_name
                if hasattr(user_tg_info, "username"):
                    username_to_display = user_tg_info.username
        except Exception as e:
            logger.debug("could not fetch full telegram user info for %s: %s", user_id, e)

    user_link = TextLink(name_to_display, url=f"tg://user?id={user_id}")
    if username_to_display:
        return Text(user_link, " (@", username_to_display, ")")
    return user_link
