import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from telecopter.logger import setup_logger
from telecopter.database import initialize_database
from telecopter.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_IDS
from telecopter.constants import CMD_START_DESCRIPTION, CMD_CANCEL_DESCRIPTION

from telecopter.handlers.main_handlers import main_router
from telecopter.handlers.admin_handlers import admin_router
from telecopter.handlers.request_handlers import request_router


logger = setup_logger(__name__)


async def set_bot_commands(bot: Bot):
    user_commands = [
        types.BotCommand(command="start", description=CMD_START_DESCRIPTION),
        types.BotCommand(command="cancel", description=CMD_CANCEL_DESCRIPTION),
    ]
    try:
        await bot.set_my_commands(user_commands, scope=types.BotCommandScopeAllPrivateChats())
        logger.info("default user bot commands set successfully for all private chats.")
    except Exception as e:
        logger.error("failed to set default user bot commands: %s", e)

    if ADMIN_CHAT_IDS:
        admin_commands = [
            types.BotCommand(command="start", description="🧑‍💼 Open Admin Panel"),
            types.BotCommand(command="cancel", description=CMD_CANCEL_DESCRIPTION),
        ]
        for admin_id in ADMIN_CHAT_IDS:
            try:
                await bot.set_my_commands(admin_commands, scope=types.BotCommandScopeChat(chat_id=admin_id))
                logger.info(f"admin commands set for admin_id {admin_id}.")
            except Exception as e:
                logger.error(f"failed to set commands for admin_id {admin_id}: %s", e)


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
    dp.include_router(admin_router)
    dp.include_router(request_router)
    dp.include_router(main_router)

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