import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from telecopter.logger import setup_logger
from telecopter.database import initialize_database
from telecopter.config import TELEGRAM_BOT_TOKEN, ADMIN_GROUP_CHAT_ID

from telecopter.handlers.admin import admin_router
from telecopter.handlers.common import common_router
from telecopter.handlers.requests import requests_router
from telecopter.handlers.report import report_problem_router


logger = setup_logger(__name__)


async def set_bot_commands(bot: Bot):
    user_commands = [
        types.BotCommand(command="start", description="🏁 Start the bot / Show main menu"),
        types.BotCommand(command="cancel", description="❌ Cancel current operation"),
    ]
    try:
        await bot.set_my_commands(user_commands)
        logger.info("user bot commands set successfully.")
    except Exception as e:
        logger.error("failed to set user bot commands: %s", e)

    if ADMIN_GROUP_CHAT_ID:
        admin_specific_commands = [
            types.BotCommand(command="announce", description="👑 Admin: Broadcast message"),
            types.BotCommand(command="announce_muted", description="👑 Admin: Broadcast silently"),
        ]
        try:
            await bot.set_my_commands(
                admin_specific_commands, scope=types.BotCommandScopeChat(chat_id=ADMIN_GROUP_CHAT_ID)
            )
            logger.info("admin-specific commands set for admin group chat id %s.", ADMIN_GROUP_CHAT_ID)
        except Exception as e:
            logger.error("failed to set admin-specific commands: %s", e)


async def main_async():
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("telegram_bot_token is not set. bot cannot start.")
        return

    logger.info("initializing database...")
    await initialize_database()
    logger.info("database initialized.")

    storage = MemoryStorage()
    default_props = DefaultBotProperties(parse_mode="HTML")
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=default_props)
    dp = Dispatcher(storage=storage)

    dp.include_router(admin_router)
    dp.include_router(requests_router)
    dp.include_router(report_problem_router)
    dp.include_router(common_router)

    await set_bot_commands(bot)

    logger.info("bot starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.critical("an error occurred while running the bot polling: %s", e, exc_info=True)
    finally:
        logger.info("bot polling stopped. closing bot session...")
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
