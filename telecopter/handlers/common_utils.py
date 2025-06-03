from typing import Optional

from aiogram import Bot
from aiogram.utils.formatting import Text
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.types import User as AiogramUser, InlineKeyboardMarkup

import telecopter.database as db
from telecopter.logger import setup_logger
from telecopter.config import ADMIN_GROUP_CHAT_ID


logger = setup_logger(__name__)


async def register_user_if_not_exists(aiogram_user: Optional[AiogramUser], chat_id: int):
    if aiogram_user:
        await db.add_or_update_user(
            user_id=aiogram_user.id, chat_id=chat_id, username=aiogram_user.username, first_name=aiogram_user.first_name
        )
        logger.debug("user %s (chat_id: %s) registration/update processed.", aiogram_user.id, chat_id)
    else:
        logger.warning("could not register user, aiogram user object is none for chat_id %s.", chat_id)


async def is_admin(user_id: int, bot: Bot) -> bool:
    if not ADMIN_GROUP_CHAT_ID:
        logger.warning("admin_group_chat_id not configured. admin check will always be false.")
        return False
    try:
        member = await bot.get_chat_member(chat_id=ADMIN_GROUP_CHAT_ID, user_id=user_id)
        allowed_statuses = [
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
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
