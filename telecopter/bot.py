import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from telecopter.logger import setup_logger
from telecopter.handlers import main_router
from telecopter.database import initialize_database
from telecopter.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID


logger = setup_logger("bot")


async def set_bot_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="Start the bot and see welcome message"),
        types.BotCommand(command="help", description="Show help message with all commands"),
        types.BotCommand(command="request", description="Request a new movie or TV show"),
        types.BotCommand(command="my_requests", description="View your past requests and their status"),
        types.BotCommand(command="report", description="Report a problem"),
        types.BotCommand(command="cancel", description="Cancel any ongoing operation"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("bot commands set successfully.")
    except Exception as e:
        logger.error("failed to set bot commands: %s", e)

    if ADMIN_CHAT_ID:
        admin_commands = commands + [
            types.BotCommand(command="announce", description="Admin: Broadcast message"),
            types.BotCommand(command="announce_muted", description="Admin: Broadcast silently"),
        ]
        try:
            await bot.set_my_commands(admin_commands, scope=types.BotCommandScopeChat(chat_id=ADMIN_CHAT_ID))
            logger.info("admin-specific commands set for admin chat id %s.", ADMIN_CHAT_ID)
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
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    dp.include_router(main_router)

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
