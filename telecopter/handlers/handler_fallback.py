from aiogram import Bot
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext


from telecopter.logger import setup_logger


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
    response_text_str = (
        f"🤔 hmm, i didn't quite get that, {first_name}.\n"
        "please use the buttons below, or type /start to see what i can do!"
    )
    await show_main_menu_for_user(message, bot, custom_text_str=response_text_str)

@handler_fallback_router.message(StateFilter(None))
async def unhandled_non_text_message_handler(message: Message, state: FSMContext, bot: Bot):
    from .main_menu import show_main_menu_for_user
    logger.info(
        "unhandled non-text message (type: %s) from user %s",
        message.content_type,
        message.from_user.id if message.from_user else "unknown",
    )
    first_name = message.from_user.first_name if message.from_user else "there"
    response_text_str = (
        f"😕 sorry {first_name}, i can only understand text messages and button presses for now.\n"
        "please use the buttons below, or type /start to see what i can do!"
    )
    await show_main_menu_for_user(message, bot, custom_text_str=response_text_str)
