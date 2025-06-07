from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from telecopter.logger import setup_logger
from telecopter.constants import AdminPanelCallback
from telecopter.handlers.common_utils import IsAdminFilter
from telecopter.handlers.admin_tasks import list_admin_tasks
from telecopter.handlers.admin_users import list_pending_users
from telecopter.handlers.admin_announce import ask_announcement_type


logger = setup_logger(__name__)

admin_panel_router = Router(name="admin_panel_router")


@admin_panel_router.callback_query(F.data == f"admin_panel:{AdminPanelCallback.VIEW_TASKS.value}", IsAdminFilter())
async def admin_panel_view_tasks_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    await callback_query.answer()
    if callback_query.message and callback_query.from_user:
        await list_admin_tasks(
            message_to_edit=callback_query.message,
            acting_user_id=callback_query.from_user.id,
            bot=bot,
            state=state,
            page=1,
        )


@admin_panel_router.callback_query(F.data == f"admin_panel:{AdminPanelCallback.MANAGE_USERS.value}", IsAdminFilter())
async def admin_panel_manage_users_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    await callback_query.answer()
    if callback_query.message:
        await list_pending_users(message_to_edit=callback_query.message, bot=bot, page=1)


@admin_panel_router.callback_query(
    F.data == f"admin_panel:{AdminPanelCallback.SEND_ANNOUNCEMENT.value}", IsAdminFilter()
)
async def admin_panel_send_announcement_cb(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    await callback_query.answer()
    if callback_query.message:
        await ask_announcement_type(callback_query.message, state, bot)
