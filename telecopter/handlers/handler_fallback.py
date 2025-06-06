from aiogram import Bot
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.utils.formatting import Text

from telecopter.logger import setup_logger
from telecopter.handlers.common_utils import is_admin
from telecopter.handlers.menu_utils import show_main_menu_for_user, show_admin_panel
from telecopter.constants import (
    MSG_FALLBACK_UNHANDLED_TEXT,
    MSG_FALLBACK_UNHANDLED_NON_TEXT,
)


logger = setup_logger(__name__)

handler_fallback_router = Router(name="handler_fallback_router")


@handler_fallback_router.message(StateFilter(None), F.text)
async def unhandled_text_message_handler(message: Message, bot: Bot):
    if not message.from_user:
        return

    if message.text and message.text.startswith("/"):
        logger.info("unhandled command from user %s: %s", message.from_user.id, message.text)
        return

    logger.info(
        "unhandled text message from user %s: %s",
        message.from_user.id,
        message.text[:50],
    )

    if await is_admin(message.from_user.id):
        await show_admin_panel(message, bot)
    else:
        first_name = message.from_user.first_name if message.from_user else "there"
        response_text_obj = Text(MSG_FALLBACK_UNHANDLED_TEXT.format(first_name=first_name))
        await show_main_menu_for_user(message, bot, custom_text_obj=response_text_obj)


@handler_fallback_router.message(StateFilter(None))
async def unhandled_non_text_message_handler(message: Message, bot: Bot):
    if not message.from_user:
        return

    logger.info(
        "unhandled non-text message (type: %s) from user %s",
        message.content_type,
        message.from_user.id,
    )

    if await is_admin(message.from_user.id):
        await show_admin_panel(message, bot)
    else:
        first_name = message.from_user.first_name if message.from_user else "there"
        response_text_obj = Text(MSG_FALLBACK_UNHANDLED_NON_TEXT.format(first_name=first_name))
        await show_main_menu_for_user(message, bot, custom_text_obj=response_text_obj)
