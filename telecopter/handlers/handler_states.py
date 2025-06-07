from aiogram.fsm.state import State, StatesGroup


class RequestMediaStates(StatesGroup):
    typing_media_name = State()
    select_media = State()
    typing_manual_request_description = State()
    confirm_media = State()
    typing_user_note = State()


class AdminBroadcastStates(StatesGroup):
    choosing_type = State()
    typing_message = State()


class AdminInteractionStates(StatesGroup):
    typing_admin_note = State()


class ReportProblemStates(StatesGroup):
    typing_problem = State()
