import asyncio
from typing import Union
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from telecopter.logger import setup_logger
from telecopter.database import initialize_database
from telecopter.config import TELEGRAM_BOT_TOKEN, ADMIN_GROUP_CHAT_ID

from telecopter.handlers import (
    admin_panel_router, admin_tasks_router, admin_announce_router, admin_moderate_router,
    core_commands_router, main_menu_router,
    media_search_router, media_submission_router,
    problem_report_router, request_history_router,
    handler_fallback_router
)

logger = setup_logger(__name__)


async def set_bot_commands(bot: Bot):
    user_commands = [
        types.BotCommand(command="start", description="🏁 start / show main menu"),
        types.BotCommand(command="cancel", description="❌ cancel current operation (if stuck)"),
    ]
    try:
        await bot.set_my_commands(user_commands, scope=types.BotCommandScopeAllPrivateChats())
        logger.info("user bot commands set successfully for private chats.")
    except Exception as e:
        logger.error("failed to set user bot commands: %s", e)

    if ADMIN_GROUP_CHAT_ID:
        admin_specific_commands_for_pm = [
            types.BotCommand(command="start", description="🏁 show admin panel"),
            types.BotCommand(command="admin", description="👑 access admin panel"),
            types.BotCommand(command="cancel", description="❌ cancel current operation"),
        ]
        # For admins in their PM with the bot, it's better to set commands based on user ID
        # or use BotCommandScopeAllAdministrators if you list them as bot admins.
        # For simplicity, we'll assume the /admin command is the primary way for admins to get their panel.
        # The /start command will also lead them there.

        # No specific commands needed for the admin group itself if interaction is through PM.
        # If you want commands IN the admin group, define them here with BotCommandScopeChat.
        # For now, focusing on PM interaction for admins.

        # To make /admin command visible to admins in PM, we could try:
        # (This requires knowing admin IDs to set scopes individually, or a global scope)
        # However, our start_command_handler will direct admins to their panel.
        # The /admin command is an additional explicit way.
    logger.info("admin commands can be accessed via /start or /admin in pm.")


async def main_async():
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("telegram_bot_token is not set. bot cannot start.")
        return

    logger.info("initializing database...")
    await initialize_database()
    logger.info("database initialized.")

    storage = MemoryStorage()
    default_props = DefaultBotProperties(parse_mode="MarkdownV2")
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=default_props)
    dp = Dispatcher(storage=storage)

    dp.include_router(core_commands_router)
    dp.include_router(main_menu_router)

    dp.include_router(admin_panel_router)
    dp.include_router(admin_tasks_router)
    dp.include_router(admin_announce_router)
    dp.include_router(admin_moderate_router)

    dp.include_router(media_search_router)
    dp.include_router(media_submission_router)
    dp.include_router(problem_report_router)
    dp.include_router(request_history_router)

    dp.include_router(handler_fallback_router)

    await set_bot_commands(bot)

    logger.info("bot starting polling...")
    try:
        allowed_updates = dp.resolve_used_update_types()
        logger.info(f"bot will listen for updates: {allowed_updates}")
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    except Exception as e:
        logger.critical("an error occurred while running the bot polling: %s", e, exc_info=True)
    finally:
        logger.info("bot polling stopped. closing bot session...")
        if bot.session and not bot.session.closed:
            await bot.session.close()
        logger.info("bot session closed.")


def main_sync():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("bot process interrupted by user (ctrl+c). shutting down.")
    except Exception as e:
        logger.critical("uncaught exception in main_sync wrapper: %s", e, exc_info=True)


if __name__ == "__main__":
    logger.info("starting bot directly via __main__...")
    main_sync()
