from aiogram import Bot
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import Text

from telecopter.logger import setup_logger
from telecopter.constants import (
    MSG_FALLBACK_UNHANDLED_TEXT,
    MSG_FALLBACK_UNHANDLED_NON_TEXT,
)

logger = setup_logger(__name__)

handler_fallback_router = Router(name="handler_fallback_router")


@handler_fallback_router.message(StateFilter(None), F.text)
async def unhandled_text_message_handler(message: Message, state: FSMContext, bot: Bot):
    from .main_menu import show_main_menu_for_user

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
    response_text_obj = Text(MSG_FALLBACK_UNHANDLED_TEXT.format(first_name=first_name))
    await show_main_menu_for_user(message, bot, custom_text_obj=response_text_obj)


@handler_fallback_router.message(StateFilter(None))
async def unhandled_non_text_message_handler(message: Message, state: FSMContext, bot: Bot):
    from .main_menu import show_main_menu_for_user

    logger.info(
        "unhandled non-text message (type: %s) from user %s",
        message.content_type,
        message.from_user.id if message.from_user else "unknown",
    )
    first_name = message.from_user.first_name if message.from_user else "there"
    response_text_obj = Text(MSG_FALLBACK_UNHANDLED_NON_TEXT.format(first_name=first_name))
    await show_main_menu_for_user(message, bot, custom_text_obj=response_text_obj)
