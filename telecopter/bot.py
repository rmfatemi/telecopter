import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from telecopter.logger import setup_logger
from telecopter.config import TELEGRAM_BOT_TOKEN
from telecopter.database import initialize_database
from telecopter.constants import CMD_START_DESCRIPTION, CMD_CANCEL_DESCRIPTION

from telecopter.handlers.main_menu import main_menu_router
from telecopter.handlers.admin_panel import admin_panel_router
from telecopter.handlers.admin_tasks import admin_tasks_router
from telecopter.handlers.admin_users import admin_users_router
from telecopter.handlers.media_search import media_search_router
from telecopter.handlers.core_commands import core_commands_router
from telecopter.handlers.problem_report import problem_report_router
from telecopter.handlers.admin_announce import admin_announce_router
from telecopter.handlers.admin_moderate import admin_moderate_router
from telecopter.handlers.request_history import request_history_router
from telecopter.handlers.media_submission import media_submission_router
from telecopter.handlers.handler_fallback import handler_fallback_router


logger = setup_logger(__name__)


async def set_bot_commands(bot: Bot):
    user_commands = [
        types.BotCommand(command="start", description=CMD_START_DESCRIPTION),
        types.BotCommand(command="cancel", description=CMD_CANCEL_DESCRIPTION),
    ]
    try:
        await bot.set_my_commands(user_commands, scope=types.BotCommandScopeAllPrivateChats())
        logger.info("user bot commands set successfully for private chats.")
    except Exception as e:
        logger.error("failed to set user bot commands: %s", e)
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
    dp.include_router(admin_users_router)
    dp.include_router(admin_announce_router)
    dp.include_router(admin_moderate_router)
    dp.include_router(media_search_router)
    dp.include_router(problem_report_router)
    dp.include_router(request_history_router)
    dp.include_router(media_submission_router)
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


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("bot process interrupted by user (ctrl+c). shutting down.")
    except Exception as e:
        logger.critical("uncaught exception in main wrapper: %s", e, exc_info=True)


if __name__ == "__main__":
    logger.info("starting bot server...")
    main()
