from typing import Union

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import Text, Bold
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, StateFilter

from telecopter.logger import setup_logger
from telecopter.handlers.common_utils import register_user_if_not_exists, is_admin


logger = setup_logger(__name__)

core_commands_router = Router(name="core_commands_router")


@core_commands_router.message(CommandStart())
async def start_command_handler(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    if message.from_user:
        await register_user_if_not_exists(message.from_user, message.chat.id)
        if await is_admin(message.from_user.id, bot):
            from telecopter.handlers.admin_panel import show_admin_panel

            await show_admin_panel(message, bot)
        else:
            from telecopter.handlers.main_menu import show_main_menu_for_user

            await show_main_menu_for_user(message, bot)


async def help_command_logic(
    event: Union[Message, CallbackQuery], state: FSMContext, bot: Bot, user_id_for_admin_check: int
):
    from telecopter.handlers.main_menu import show_main_menu_for_user

    await state.clear()
    help_text_content_list = [
        Bold("❓ how to use telecopter bot:"),
        Text("\n\nuse the main menu buttons to navigate:\n"),
        Text("\n🎬 "),
        Bold("request media:"),
        Text(" find and request new movies or tv shows."),
        Text("\n📊 "),
        Bold("my requests:"),
        Text(" check the status of your past requests."),
        Text("\n⚠️ "),
        Bold("report a problem:"),
        Text(" let us know if something is wrong."),
        Text("\n\npress /start anytime to see the main menu."),
        Text("\nuse the 'cancel' button in operations or from the main menu to stop any current action."),
    ]
    if await is_admin(user_id_for_admin_check, bot):
        help_text_content_list.extend(
            [
                Text("\n\n👑 "),
                Bold("admin info:"),
                Text(
                    " access the admin panel via the /admin command or from the /start menu to manage tasks and send"
                    " announcements."
                ),
            ]
        )

    help_text_formatted = Text(*help_text_content_list)
    await show_main_menu_for_user(event, bot, custom_text_html=help_text_formatted.as_html())


@core_commands_router.message(Command("cancel"), StateFilter("*"))
@core_commands_router.callback_query(F.data.in_({"action_cancel", "main_menu:cancel_current_action"}), StateFilter("*"))
async def universal_cancel_handler(event: Union[Message, CallbackQuery], state: FSMContext, bot: Bot):
    from telecopter.handlers.main_menu import show_main_menu_for_user

    user_id = event.from_user.id if event.from_user else "unknown"
    current_state_str = await state.get_state()
    action_cancelled_text_str = "✅ action cancelled. what can i help you with next?"

    if current_state_str is not None:
        logger.info("user %s cancelled conversation from state %s.", user_id, current_state_str)
        await state.clear()
        if isinstance(event, CallbackQuery) and event.message:
            await event.answer("action cancelled.", show_alert=False)
        await show_main_menu_for_user(event, bot, custom_text_str=action_cancelled_text_str)

    else:
        logger.info("user %s used cancel outside of a conversation.", user_id)
        no_active_action_text_str = "🤷 no active operation to cancel. here's the main menu:"
        if isinstance(event, CallbackQuery):
            await event.answer("no active operation.", show_alert=False)
        await show_main_menu_for_user(event, bot, custom_text_str=no_active_action_text_str)
