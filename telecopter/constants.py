USER_STATUS_NEW = "new"
USER_STATUS_REJECTED = "rejected"
USER_STATUS_APPROVED = "approved"
USER_STATUS_PENDING_APPROVAL = "pending_approval"

REQUEST_STATUS_COMPLETED = "completed"
REQUEST_TYPE_USER_APPROVAL = "user_approval"
REQUEST_STATUS_PENDING_ADMIN = "pending_admin"

CALLBACK_USER_ACCESS_REQUEST_PREFIX = "user_access"
CALLBACK_USER_ACCESS_REQUEST_ACTION = "request"
CALLBACK_USER_ACCESS_LATER_ACTION = "later"

CALLBACK_USER_APPROVAL_TASK_ACTION_PREFIX = "usr_app_task"
CALLBACK_USER_APPROVAL_TASK_APPROVE = "approve"
CALLBACK_USER_APPROVAL_TASK_REJECT = "reject"


CALLBACK_ADMIN_PANEL_PREFIX = "admin_panel"
CALLBACK_ADMIN_PANEL_VIEW_TASKS = "view_tasks"
CALLBACK_ADMIN_PANEL_SEND_ANNOUNCEMENT = "send_announcement"

CALLBACK_ADMIN_TASKS_PAGE_PREFIX = "admin_tasks_page"
CALLBACK_ADMIN_TASKS_BACK_PANEL = "admin_tasks_back_panel"
CALLBACK_ADMIN_TASK_MODERATE_PREFIX = "admin_task_moderate"
CALLBACK_ADMIN_REVIEW_USER_APPROVAL_PREFIX = "admin_review_usr_app"


CALLBACK_ACTION_CANCEL = "action_cancel"
CALLBACK_MAIN_MENU_CANCEL_ACTION = "main_menu:cancel_current_action"
CALLBACK_MAIN_MENU_REQUEST_MEDIA = "main_menu:request_media"
CALLBACK_MAIN_MENU_MY_REQUESTS = "main_menu:my_requests"
CALLBACK_MAIN_MENU_REPORT_PROBLEM = "main_menu:report_problem"
CALLBACK_MAIN_MENU_SHOW_HELP = "main_menu:show_help"
CALLBACK_MAIN_MENU_SHOW_START_MENU_FROM_MY_REQUESTS = "main_menu:show_start_menu_from_my_requests"

FSM_STATE_KEY_TARGET_USER_ID = "target_user_id"
FSM_STATE_KEY_TARGET_USER_NAME = "target_user_name"


BTN_REQUEST_ACCESS = "👍 Request Access"
BTN_MAYBE_LATER = "⏱️ Maybe Later"
BTN_APPROVE_USER_ACTION = "✅ Approve User"
BTN_REJECT_USER_ACTION = "❌ Reject User"
BTN_APPROVE_USER_DYNAMIC = "✅ Approve {user_name}"
BTN_REJECT_USER_DYNAMIC = "❌ Reject {user_name}"
BTN_VIEW_TASKS = "📋 View Tasks"
BTN_SEND_ANNOUNCEMENT = "📢 Send Announcement"
BTN_LIST_PENDING_APPROVALS = "⏳ List Pending Approvals"
BTN_PREVIOUS_PAGE = "⬅️ Previous"
BTN_NEXT_PAGE = "Next ➡️"
BTN_PREVIOUS_TASKS = "⬅️ Previous Tasks"
BTN_NEXT_TASKS = "Next Tasks ➡️"
BTN_BACK_TO_ADMIN_PANEL = "⬅️ Back to Admin Panel"
BTN_BACK_TO_MAIN_MENU = "⬅️ Back to Main Menu"
BTN_YES_REQUEST_IT = "✅ Yes, Request It"
BTN_YES_WITH_NOTE = "📝 Yes, with a Note"
BTN_NO_CANCEL = "❌ No, Cancel"
BTN_OTHER_MANUAL_REQUEST = "📝 Other / Not Found - Manual Request"
BTN_CANCEL_REQUEST = "❌ Cancel Request"
BTN_ANNOUNCE_UNMUTED = "🔊 Unmuted"
BTN_ANNOUNCE_MUTED = "🤫 Muted"
BTN_ANNOUNCE_CANCEL = "❌ Cancel"
BTN_MOD_APPROVE = "✅ Approve"
BTN_MOD_APPROVE_W_NOTE = "📝 Approve w/ Note"
BTN_MOD_DENY = "❌ Deny"
BTN_MOD_DENY_W_NOTE = "📝 Deny w/ Note"
BTN_MOD_MARK_COMPLETED = "🏁 Mark Completed"
BTN_MOD_COMPLETE_W_NOTE = "📝 Complete w/ Note"
BTN_MOD_SHELVING_DECISION = "Shelving Decision"
BTN_MOD_ACKNOWLEDGE = "👀 Acknowledge"
BTN_MOD_MARK_RESOLVED = "🛠️ Mark Resolved"
BTN_MOD_RESOLVE_W_NOTE = "📝 Resolve w/ Note"
BTN_REVIEW_USER_APPROVAL_TASK = "👤 Review User Approval"


MSG_ACCESS_DENIED = "Access denied\."
MSG_NOT_AUTHORIZED_ALERT = "Not authorized"
MSG_ERROR_UNEXPECTED = "❗ Sorry, an unexpected error occurred\. Please try again later\."
MSG_ERROR_PROCESSING_ACTION_ALERT = "Error processing action\."
MSG_ERROR_INVALID_CALLBACK_ALERT = "Error processing action\."
MSG_ACTION_CANCELLED_ALERT = "Action cancelled\."
MSG_ACTION_CANCELLED_MENU = "✅ Action cancelled\. What can I help you with next?"
MSG_NO_ACTIVE_OPERATION_ALERT = "No active operation\."
MSG_NO_ACTIVE_OPERATION_MENU = "🤷 No active operation to cancel\. Here's the main menu:"
MSG_ADMIN_ONLY_ACTION = "⛔ This action is admin-only\."


MSG_START_WELCOME_NEW_PROMPT = (
    "👋 Welcome, {user_name}\! To use this bot, you need to request access from an administrator\. Would you like"
    " to request access now?"
)
MSG_START_PENDING_APPROVAL = (
    "👋 Hello {user_name}, your account is still pending approval\. You'll be notified once it's reviewed\."
)
MSG_START_REJECTED = "😕 Hello {user_name}, access to this bot has not been granted to your account\."
MSG_START_UNEXPECTED_STATUS_ERROR = "An unexpected error occurred with your account status\. Please try again later\."
MSG_USER_ACCESS_REQUEST_SUBMITTED = (
    "✅ Your request for access has been submitted and is awaiting admin review\. You'll be notified once an"
    " administrator reviews it\."
)
MSG_USER_ACCESS_REQUEST_SUBMITTED_ALERT = "Request submitted\!"
MSG_USER_ACCESS_DEFERRED = "👍 Okay\. You can request access later by typing /start again\."
MSG_USER_ACCESS_DEFERRED_ALERT = "Action deferred\."
MSG_USER_APPROVED_NOTIFICATION = "🎉 Your account has been approved\! You can now use the bot\. Try /start"
MSG_USER_REJECTED_NOTIFICATION = (
    "🙁 Your account access request has been reviewed and was not approved at this time\. You will not be able to use"
    " this bot\."
)
MSG_USER_ACCESS_PENDING_INFO = (
    "⏳ Your account is still pending approval by an administrator\. You'll be notified once it's reviewed\."
)
MSG_USER_REJECTED_INFO = "❌ Access to this bot has not been granted to your account\."
MSG_USER_NEW_INFO_START_REQUIRED = "👋 Welcome\! Please /start the bot to request access\."
MSG_USER_UNKNOWN_STATUS_INFO = (
    "⚠️ An issue occurred with your account status\. Please contact support or try /start again\."
)


TITLE_ADMIN_PANEL = "👑 Admin Panel"
TITLE_PENDING_USERS_LIST = "Users Pending Approval (Page {page}/{total_pages})"
MSG_NO_PENDING_USERS_PAGE_1 = "\n🎉 No users are currently pending approval\."
MSG_NO_PENDING_USERS_OTHER_PAGE = "\nNo more pending users found on page {page}\."
TITLE_ADMIN_TASKS_LIST = "📋 Admin Tasks (Page {page} of {total_pages})"
MSG_NO_ADMIN_TASKS_PAGE_1 = "🎉 No pending tasks for admins at the moment\!"
MSG_NO_ADMIN_TASKS_OTHER_PAGE = "✅ No more tasks found on page {page}\."
MSG_NO_TASKS_INFO_TO_DISPLAY = "No tasks information to display\."


MSG_ADMIN_NOTIFY_NEW_USER_TASK_TITLE = "🆕 Task: New User Approval Request"
MSG_ADMIN_NOTIFY_USER_LABEL = "User: "
MSG_ADMIN_NOTIFY_USER_ID_LABEL = "\nUser ID: `{user_id}`"
MSG_ADMIN_NOTIFY_TASK_ID_LABEL = "\nTask ID: `{task_id}`"
MSG_ADMIN_NOTIFY_PLEA = "\n\nPlease review via tasks or use quick actions below\."
MSG_ADMIN_USER_APPROVED_CONFIRM = "✅ User {user_name} (ID: {user_id}) has been approved\. Task {task_id} closed\."
MSG_ADMIN_USER_REJECTED_CONFIRM = "❌ User {user_name} (ID: {user_id}) has been rejected\. Task {task_id} closed\."
MSG_ADMIN_USER_NOTIFY_FAIL_SUFFIX = " (failed to notify user)"
MSG_ADMIN_TARGET_USER_NOT_FOUND_ALERT = "Target user not found\."
MSG_ADMIN_UNKNOWN_ACTION_ALERT = "Unknown action\."
MSG_ADMIN_USER_APPROVAL_TASK_DETAILS_TITLE = "👤 User Approval Task Details (ID: {task_id})"
MSG_ADMIN_USER_APPROVAL_TASK_USER_INFO_LABEL = "User to approve/reject: "
MSG_TASK_ALREADY_PROCESSED_ALERT = "Task already processed\."
MSG_TASK_ALREADY_PROCESSED_EDIT = "This task (ID: {task_id}) was already completed with status: {status}\."
MSG_USER_ALREADY_APPROVED_ALERT = "User already approved\."
MSG_USER_ALREADY_APPROVED_EDIT = "User {user_name} (ID: {user_id}) was already approved\. Task {task_id} closed\."
MSG_USER_ALREADY_REJECTED_ALERT = "User already rejected\."
MSG_USER_ALREADY_REJECTED_EDIT = "User {user_name} (ID: {user_id}) was already rejected\. Task {task_id} closed\."


PROMPT_ADMIN_ANNOUNCE_TYPE = "📢 Choose announcement type:"
PROMPT_ADMIN_ANNOUNCE_TYPING_MESSAGE = (
    "✍️ Please type your {muted_status} announcement message below\. You can cancel from the admin panel if you return"
    " via /start\."
)
MSG_ADMIN_ANNOUNCE_CANCELLED = "Announcement cancelled\."
MSG_ADMIN_ANNOUNCE_NO_USERS = "👥 No registered users found to send announcement to\."
MSG_ADMIN_ANNOUNCE_SENT_CONFIRM = "✅ Announcement sent to {sent_count} users\."
MSG_ADMIN_ANNOUNCE_FAILURES_SUFFIX = " {failed_count} failures\."


MSG_ADMIN_TASK_CLOSED_IN_VIEW = "Task ID {request_id} closed in this view\."
MSG_ADMIN_REQUEST_NOT_FOUND = "❗Error: Request ID {request_id} not found\."
MSG_ADMIN_TASK_IDENTIFY_ERROR = "Error: Could not identify the task\."
MSG_ADMIN_TASK_USER_NOT_FOUND_ERROR = "Error: User for task ID {request_id} not found\."
PROMPT_ADMIN_NOTE_FOR_REQUEST = (
    "✍️ Please send the note for request ID {request_id} to be {base_action_key}d\. You can cancel from the admin panel"
    " if you return via /start\."
)
MSG_ADMIN_CONTEXT_ERROR_FOR_NOTE = "❗Error: Could not retrieve context for adding note\. Please try the action again\."
MSG_ADMIN_ACTION_WITH_NOTE_PROCESSED = "✅ Action (with note) for request ID {request_id} processed: {log_message}"
MSG_ADMIN_MODERATE_UPDATE_FALLBACK = "Update for request ID {request_id}: {log_message} (Note: {admin_note})"


MSG_HELP_TITLE = "❓ How to Use Telecopter Bot:"
MSG_HELP_NAVIGATION = "\n\nUse the main menu buttons to navigate:\n"
MSG_HELP_REQUEST_MEDIA_ICON = "\n🎬 "
MSG_HELP_REQUEST_MEDIA_TITLE = "Request Media:"
MSG_HELP_REQUEST_MEDIA_DESC = " Find and request new movies or TV shows\."
MSG_HELP_MY_REQUESTS_ICON = "\n📊 "
MSG_HELP_MY_REQUESTS_TITLE = "My Requests:"
MSG_HELP_MY_REQUESTS_DESC = " Check the status of your past requests\."
MSG_HELP_REPORT_PROBLEM_ICON = "\n⚠️ "
MSG_HELP_REPORT_PROBLEM_TITLE = "Report a Problem:"
MSG_HELP_REPORT_PROBLEM_DESC = " Let us know if something is wrong\."
MSG_HELP_START_ANYTIME = "\n\nPress /start anytime to see the main menu\."
MSG_HELP_CANCEL_ACTION = "\nUse the 'Cancel' button in operations or from the main menu to stop any current action\."
MSG_HELP_ADMIN_INFO_ICON = "\n\n👑 "
MSG_HELP_ADMIN_INFO_TITLE = "Admin Info:"
MSG_HELP_ADMIN_INFO_DESC = (
    " Access the admin panel via the /admin command or from the /start menu to manage tasks and send announcements\."
)


MSG_MAIN_MENU_DEFAULT_WELCOME = "👋 Hello {user_first_name}\! What can I help you with?"
MSG_MAIN_MENU_MEDIA_SEARCH_UNAVAILABLE = "⚠️ Media search is currently unavailable\. Please try again later\."
MSG_MAIN_MENU_BACK_WELCOME = "👋 Welcome back to the main menu, {user_first_name}\!"
PROMPT_MAIN_MENU_REQUEST_MEDIA = "✍️ What movie or TV show are you looking for? Please type the name below\."
BTN_MAIN_MENU_REQUEST_MEDIA = "🎬 Request Media"
BTN_MAIN_MENU_MY_REQUESTS = "📊 My Requests"
BTN_MAIN_MENU_REPORT_PROBLEM = "⚠️ Report a Problem"
BTN_MAIN_MENU_HELP = "❓ Help"
BTN_MAIN_MENU_CANCEL_ACTION = "❌ Cancel Action"


PROMPT_PROBLEM_REPORT_DESCRIPTION = (
    "📝 Please describe the problem you are experiencing below, or use the cancel button in the menu\."
)
MSG_PROBLEM_REPORT_SUBMITTED = "✅ Your problem report has been submitted\. Thank you\!"
MSG_PROBLEM_REPORT_SUBMITTED_MENU_PROMPT = "✅ Report submitted\! What can I help you with next?"
PROMPT_PROBLEM_REPORT_TYPE_DESCRIPTION = (
    "✍️ Please type your problem description, or use the cancel button in the menu\."
)
ERR_PROBLEM_REPORT_TOO_SHORT = (
    "✍️ Your description seems a bit short\. Please provide more details to help us understand the issue, or use the"
    " cancel button in the menu\."
)

CMD_START_DESCRIPTION = "🏁 Start / Show Main Menu"
CMD_CANCEL_DESCRIPTION = "❌ Cancel Current Operation (if stuck)"

PROMPT_MEDIA_NAME_TYPING = (
    "✍️ Please type the name of the media you're looking for\. You can cancel using the main menu\."
)
ERR_MEDIA_QUERY_TOO_SHORT = "✍️ Your search query is too short\. Please try a more specific name\."
MSG_MEDIA_SEARCHING = '🔎 Searching for "{query_text}"\.\.\.'
MSG_MEDIA_NO_RESULTS = (
    "😕 Sorry, I couldn't find any results for \"{query_text}\"\. You can try a different name, or choose 'Other / Not"
    " Found'\."
)
MSG_MEDIA_RESULTS_FOUND = '🔍 Here\'s what I found for "{query_text}"\. Please select one:'
PROMPT_MANUAL_REQUEST_DESCRIPTION = (
    "✍️ Okay, you chose 'Other / Not Found'\. Please describe the media you're looking for (e\.g\., title, year, any"
    ' details)\. Your original search term was: "{original_query}"\. This will be sent as a manual request\.'
)
ERR_MEDIA_DETAILS_FETCH_FAILED = "🔎❗ Sorry, I couldn't fetch details\. Please try another selection or search again\."
ERR_CALLBACK_INVALID_MEDIA_SELECTION = "❗ Oops\! An error occurred\. Please try searching again\."
MSG_MEDIA_CONFIRM_REQUEST = "🎯 Confirm: Do you want to request this?"

PROMPT_MANUAL_REQUEST_TYPE_DESCRIPTION = "✍️ Please provide a description for your manual request\."
ERR_MANUAL_REQUEST_DESCRIPTION_TOO_SHORT = "✍️ Your description is a bit short\. Please provide more details\."
MSG_MANUAL_REQUEST_SUBMITTED = '✅ Your manual request for "{description}" has been submitted\. Admins will review it\.'
MSG_MANUAL_REQUEST_SUBMITTED_MENU_PROMPT = "✅ Manual request submitted\! What can I help you with next?"
ERR_SELECTION_EXPIRED = "⏳ Error: Your selection seems to have expired\. Please start over\."
ERR_SELECTION_EXPIRED_MENU_PROMPT = "⏳ Selection expired\. What can I help you with next?"
PROMPT_USER_NOTE_FOR_REQUEST = "📝 Please send a short note for your request\."
MSG_REQUEST_SUBMITTED_FOR_REVIEW = "✅ Your request has been submitted for review\. You'll be notified\!"
MSG_REQUEST_SUBMITTED_MENU_PROMPT = "✅ Request submitted\! What can I help you with next?"
MSG_REQUEST_WITH_NOTE_SUBMITTED = "✅ Your request with the note has been submitted\. You'll be notified\!"

MSG_REQ_HISTORY_NO_REQUESTS = "🤷 You haven't made any requests or reports yet\."
MSG_REQ_HISTORY_NO_MORE_REQUESTS_ON_PAGE = "✅ No more requests found on page {page}\."
MSG_REQ_HISTORY_TITLE = "📖 Your Requests & Reports (Page {page} of {total_pages})"
MSG_REQ_HISTORY_NO_REQUESTS_TO_DISPLAY = "🤷 No requests to display\."
ERR_REQ_HISTORY_UPDATE_FAILED = "❗Could not update the request list\."
ERR_REQ_HISTORY_GENERIC = "❗An error occurred\."

MSG_FALLBACK_UNHANDLED_TEXT = (
    "🤔 Hmm, I didn't quite get that, {first_name}\. Please use the buttons below, or type /start to see what I can"
    " do\!"
)
MSG_FALLBACK_UNHANDLED_NON_TEXT = (
    "😕 Sorry {first_name}, I can only understand text messages and button presses for now\. Please use the buttons"
    " below, or type /start to see what I can do\!"
)
