# USER STATUS
USER_STATUS_APPROVED = "approved"
USER_STATUS_NEW = "new"
USER_STATUS_PENDING_APPROVAL = "pending_approval"
USER_STATUS_REJECTED = "rejected"

# REQUEST STATUS & TYPE
REQUEST_STATUS_COMPLETED = "completed"
REQUEST_STATUS_PENDING_ADMIN = "pending_admin"
REQUEST_TYPE_USER_APPROVAL = "user_approval"

# CALLBACK ACTIONS
CALLBACK_ACTION_CANCEL = "action_cancel"

# CALLBACK ADMIN PANEL
CALLBACK_ADMIN_PANEL_PREFIX = "admin_panel"
CALLBACK_ADMIN_PANEL_SEND_ANNOUNCEMENT = "send_announcement"
CALLBACK_ADMIN_PANEL_VIEW_TASKS = "view_tasks"

# CALLBACK ADMIN REVIEW USER APPROVAL
CALLBACK_ADMIN_REVIEW_USER_APPROVAL_PREFIX = "admin_review_usr_app"

# CALLBACK ADMIN TASKS
CALLBACK_ADMIN_TASKS_BACK_PANEL = "admin_tasks_back_panel"
CALLBACK_ADMIN_TASKS_PAGE_PREFIX = "admin_tasks_page"
CALLBACK_ADMIN_TASK_MODERATE_PREFIX = "admin_task_moderate"

# CALLBACK MAIN MENU
CALLBACK_MAIN_MENU_CANCEL_ACTION = "main_menu:cancel_current_action"

# CALLBACK USER ACCESS REQUEST
CALLBACK_USER_ACCESS_LATER_ACTION = "later"
CALLBACK_USER_ACCESS_REQUEST_ACTION = "request"
CALLBACK_USER_ACCESS_REQUEST_PREFIX = "user_access"

# CALLBACK USER APPROVAL TASK
CALLBACK_USER_APPROVAL_TASK_ACTION_PREFIX = "usr_app_task"
CALLBACK_USER_APPROVAL_TASK_APPROVE = "approve"
CALLBACK_USER_APPROVAL_TASK_REJECT = "reject"

# BUTTON LABELS
BTN_ANNOUNCE_CANCEL = "❌ Cancel"
BTN_ANNOUNCE_MUTED = "🤫 Muted"
BTN_ANNOUNCE_UNMUTED = "🔊 Unmuted"
BTN_APPROVE_USER_ACTION = "✅ Approve User"
BTN_BACK_TO_ADMIN_PANEL = "⬅️ Back to Admin Panel"
BTN_BACK_TO_MAIN_MENU = "⬅️ Back to Main Menu"
BTN_CANCEL_ACTION = "❌ Cancel Action"
BTN_CONFIRM_REQUEST = "✅ Yes, request it"
BTN_CONFIRM_WITH_NOTE = "📝 Yes, with a note"
BTN_MAYBE_LATER = "⏱️ Maybe Later"
BTN_MEDIA_MANUAL_REQUEST = "📝 Other / not found - manual request"
BTN_MOD_ACKNOWLEDGE = "👀 Acknowledge"
BTN_MOD_APPROVE = "✅ Approve"
BTN_MOD_APPROVE_W_NOTE = "📝 Approve w/ Note"
BTN_MOD_COMPLETE_W_NOTE = "📝 Complete w/ Note"
BTN_MOD_DENY = "❌ Deny"
BTN_MOD_DENY_W_NOTE = "📝 Deny w/ Note"
BTN_MOD_MARK_COMPLETED = "🏁 Mark Completed"
BTN_MOD_MARK_RESOLVED = "🛠️ Mark Resolved"
BTN_MOD_RESOLVE_W_NOTE = "📝 Resolve w/ Note"
BTN_MOD_SHELVING_DECISION = "Shelving Decision"
BTN_MY_REQUESTS = "📊 My Requests"
BTN_NEXT_PAGE = "Next ➡️"
BTN_NEXT_TASKS = "Next Tasks ➡️"
BTN_PREVIOUS_PAGE = "⬅️ Previous"
BTN_PREVIOUS_TASKS = "⬅️ Previous Tasks"
BTN_REJECT_USER_ACTION = "❌ Reject User"
BTN_REPORT_PROBLEM = "⚠️ Report a Problem"
BTN_REQUEST_ACCESS = "👍 Request Access"
BTN_REQUEST_MEDIA = "🎬 Request Media"
BTN_REVIEW_USER_APPROVAL_TASK = "👤 Review User Approval"
BTN_SEND_ANNOUNCEMENT = "📢 Send Announcement"
BTN_VIEW_TASKS = "📋 View Tasks"

# COMMAND DESCRIPTIONS
CMD_CANCEL_DESCRIPTION = "❌ Cancel Current Operation (if stuck)"
CMD_START_DESCRIPTION = "🏁 Start / Show Main Menu"

# ERROR MESSAGES
ERR_CALLBACK_INVALID_MEDIA_SELECTION = "❗ Oops! An error occurred. Please try searching again."
ERR_MANUAL_REQUEST_TOO_SHORT = "✍️ Your description is a bit short. Please provide more details."
ERR_MEDIA_DETAILS_FETCH_FAILED = "🔎❗ Sorry, I couldn't fetch details. Please try another selection or search again."
ERR_MEDIA_QUERY_TOO_SHORT = "✍️ Your search query is too short. Please try a more specific name."
ERR_PROBLEM_DESCRIPTION_TOO_SHORT = (
    "✍️ Your description seems a bit short. Please provide more details to help us understand the issue, or use the"
    " cancel button in the menu."
)
ERR_REQUEST_EXPIRED = "⏳ Error: Your selection seems to have expired. Please start over."

# MSG_ACCESS & AUTHORIZATION
MSG_ACCESS_DENIED = "Access denied."
MSG_NOT_AUTHORIZED_ALERT = "Not authorized"

# MSG_ACTION
MSG_ACTION_CANCELLED_ALERT = "Action cancelled."
MSG_ACTION_CANCELLED_MENU = "✅ Action cancelled. What can I help you with next?"

# MSG_ADMIN
MSG_ADMIN_ACTION_DB_UPDATE_FAILED = "❗ Failed to update DB status for request ID {request_id} to {new_status}"
MSG_ADMIN_ACTION_DB_UPDATE_FAILED_WITH_NOTE = (
    "❗ Failed to update DB status for request ID {request_id} to {new_status} with note"
)
MSG_ADMIN_ACTION_ERROR = "❗ Unexpected error processing request {request_id}"
MSG_ADMIN_ACTION_NOTIFICATION_FAILED = " (User notification failed)"
MSG_ADMIN_ACTION_SUCCESS = "Request ID {request_id} status set to {new_status}"
MSG_ADMIN_ACTION_SUCCESS_WITH_NOTE = "Request ID {request_id} status set to {new_status} with note"
MSG_ADMIN_ACTION_TAKEN_BY = "Action taken by "
MSG_ADMIN_ACTION_TAKEN_SUFFIX = ": {action}"
MSG_ADMIN_ACTION_UNKNOWN = "❗ Unknown action '{action_full_key}' for request ID {request_id}."
MSG_ADMIN_ACTION_UNKNOWN_STATUS = "❗ Unknown new_status '{new_status}' or missing template for request ID {request_id}"
MSG_ADMIN_ACTION_USER_NOT_FOUND = " (User chat_id not found)"
MSG_ADMIN_ANNOUNCE_CANCELLED = "Announcement cancelled."
MSG_ADMIN_ANNOUNCE_FAILURES_SUFFIX = " {failed_count} failures."
MSG_ADMIN_ANNOUNCE_NO_USERS = "👥 No registered users found to send announcement to."
MSG_ADMIN_ANNOUNCE_SENT_CONFIRM = "✅ Announcement sent to {sent_count} users."
MSG_ADMIN_CONTEXT_ERROR_FOR_NOTE = "❗Error: Could not retrieve context for adding note. Please try the action again."
MSG_ADMIN_MESSAGE_DIVIDER = "\n\n---\n"
MSG_ADMIN_MODERATE_UPDATE_FALLBACK = "Update for request ID {request_id}: {log_message} (Note: {admin_note})"
MSG_ADMIN_NOTE_LABEL = "Admin's note:"
MSG_ADMIN_NOTIFY_NEW_USER_TASK_TITLE = "🆕 Task: New User Approval Request"
MSG_ADMIN_NOTIFY_PLEA = "\n\nPlease review via tasks or use quick actions below."
MSG_ADMIN_NOTIFY_TASK_ID_LABEL = "\nTask ID: `{task_id}`"
MSG_ADMIN_NOTIFY_USER_ID_LABEL = "\nUser ID: `{user_id}`"
MSG_ADMIN_NOTIFY_USER_LABEL = "User: "
MSG_ADMIN_ONLY_ACTION = "⛔ This action is admin-only."
MSG_ADMIN_REQUEST_NOT_FOUND = "❗Error: Request ID {request_id} not found."
MSG_ADMIN_TARGET_USER_NOT_FOUND_ALERT = "Target user not found."
MSG_ADMIN_TASK_CLOSED_IN_VIEW = "Task ID {request_id} closed in this view."
MSG_ADMIN_TASK_IDENTIFY_ERROR = "Error: Could not identify the task."
MSG_ADMIN_TASK_USER_NOT_FOUND_ERROR = "Error: User for task ID {request_id} not found."
MSG_ADMIN_UNKNOWN_ACTION_ALERT = "Unknown action."
MSG_ADMIN_USER_APPROVED_CONFIRM = "✅ User {user_name} (ID: {user_id}) has been approved. Task {task_id} closed."
MSG_ADMIN_USER_APPROVAL_TASK_DETAILS_TITLE = "👤 User Approval Task Details (ID: {task_id})"
MSG_ADMIN_USER_APPROVAL_TASK_USER_INFO_LABEL = "User to approve/reject: "
MSG_ADMIN_USER_NOTIFY_FAIL_SUFFIX = " (failed to notify user)"
MSG_ADMIN_USER_REJECTED_CONFIRM = "❌ User {user_name} (ID: {user_id}) has been rejected. Task {task_id} closed."
MSG_ADMIN_ACTION_WITH_NOTE_PROCESSED = "✅ Action (with note) for request ID {request_id} processed: {log_message}"

# MSG_ERROR
MSG_ERROR_PROCESSING_ACTION_ALERT = "Error processing action."
MSG_ERROR_UNEXPECTED = "❗ Sorry, an unexpected error occurred. Please try again later."

# MSG_FALLBACK
MSG_FALLBACK_UNHANDLED_NON_TEXT = (
    "😕 Sorry {first_name}, I can only understand text messages and button presses for now. Please use the buttons"
    " below, or type /start to see what I can do!"
)
MSG_FALLBACK_UNHANDLED_TEXT = (
    "🤔 Hmm, I didn't quite get that, {first_name}. Please use the buttons below, or type /start to see what I can do!"
)

# MSG_MAIN_MENU
MSG_MAIN_MENU_BACK_WELCOME = "👋 Welcome back to the main menu, {user_first_name}!"
MSG_MAIN_MENU_DEFAULT_WELCOME = "👋 Hello {user_first_name}! What can I help you with?"
MSG_MAIN_MENU_MEDIA_SEARCH_UNAVAILABLE = "⚠️ Media search is currently unavailable. Please try again later."

# MSG_MANUAL_REQUEST
MSG_MANUAL_REQUEST_SUBMITTED = '✅ Your manual request for "{description}" has been submitted. Admins will review it.'
MSG_MANUAL_REQUEST_SUCCESS = "✅ Manual request submitted! What can I help you with next?"

# MSG_MEDIA
MSG_MEDIA_CONFIRM_REQUEST = "🎯 Confirm: Do you want to request this?"
MSG_MEDIA_NO_RESULTS = (
    "😕 Sorry, I couldn't find any results for \"{query_text}\". You can try a different name, or choose 'Other / Not"
    " Found'."
)
MSG_MEDIA_RESULTS_FOUND = '🔍 Here\'s what I found for "{query_text}". Please select one:'
MSG_MEDIA_SEARCHING = '🔎 Searching for "{query_text}"...'

# MSG_NO_
MSG_NO_ACTIVE_OPERATION_ALERT = "No active operation."
MSG_NO_ACTIVE_OPERATION_MENU = "🤷 No active operation to cancel. Here's the main menu:"
MSG_NO_ADMIN_TASKS_OTHER_PAGE = "✅ No more tasks found on page {page}."
MSG_NO_ADMIN_TASKS_PAGE_1 = "🎉 No pending tasks for admins at the moment!"
MSG_NO_MORE_REQUESTS = "✅ No more requests found on page {page}."
MSG_NO_REQUESTS_YET = "🤷 You haven't made any requests or reports yet."
MSG_NO_TASKS_INFO_TO_DISPLAY = "No tasks information to display."

# MSG_PROBLEM_REPORT
MSG_REPORT_SUBMITTED = "✅ Your problem report has been submitted. Thank you!"
MSG_REPORT_SUCCESS = "✅ Report submitted! What can I help you with next?"

# MSG_REQ_HISTORY
MSG_REQUESTS_PAGE_HEADER = "📖 Your requests & reports (page {page} of {total_pages})"

# MSG_REQUEST
MSG_REQUEST_SUBMITTED = "✅ Your request has been submitted for review. You'll be notified!"
MSG_REQUEST_SUCCESS = "✅ Request submitted! What can I help you with next?"
MSG_REQUEST_WITH_NOTE_SUBMITTED = "✅ Your request with the note has been submitted. You'll be notified!"

# MSG_SELECTION_EXPIRED
MSG_SELECTION_EXPIRED = "⏳ Selection expired. What can I help you with next?"

# MSG_START
MSG_START_PENDING_APPROVAL = (
    "👋 Hello {user_name}, Your account is still pending approval. You'll be notified once it's reviewed."
)
MSG_START_REJECTED = "😕 Hello {user_name}, Access to this bot has not been granted to your account."
MSG_START_UNEXPECTED_STATUS_ERROR = "An unexpected error occurred with your account status. Please try again later."
MSG_START_WELCOME_NEW_PROMPT = (
    "👋 Welcome, {user_name}! To use this bot, you need to request access from an administrator. Would you like"
    " to request access now?"
)

# MSG_TASK
MSG_TASK_ALREADY_PROCESSED_ALERT = "Task already processed."
MSG_TASK_ALREADY_PROCESSED_EDIT = "This task (ID: {task_id}) was already completed with status: {status}."

# MSG_USER
MSG_USER_ACCESS_DEFERRED = "👍 Okay. You can request access later by typing /start again."
MSG_USER_ACCESS_DEFERRED_ALERT = "Action deferred."
MSG_USER_ACCESS_PENDING_INFO = (
    "⏳ Your account is still pending approval by an administrator. You'll be notified once it's reviewed."
)
MSG_USER_ACCESS_REQUEST_SUBMITTED = (
    "✅ Your request for access has been submitted and is awaiting admin review. You'll be notified once an"
    " administrator reviews it."
)
MSG_USER_ACCESS_REQUEST_SUBMITTED_ALERT = "Request submitted!"
MSG_USER_ALREADY_APPROVED_ALERT = "User already approved."
MSG_USER_ALREADY_APPROVED_EDIT = "User {user_name} (ID: {user_id}) was already approved. Task {task_id} closed."
MSG_USER_ALREADY_REJECTED_ALERT = "User already rejected."
MSG_USER_ALREADY_REJECTED_EDIT = "User {user_name} (ID: {user_id}) was already rejected. Task {task_id} closed."
MSG_USER_APPROVED_NOTIFICATION = "🎉 Your account has been approved! You can now use the bot. Try /start"
MSG_USER_NEW_INFO_START_REQUIRED = "👋 Welcome! Please /start the bot to request access."
MSG_USER_PROBLEM_ACKNOWLEDGED = '👀 Update: Your problem report "{title}" has been acknowledged by the admin.'
MSG_USER_PROBLEM_RESOLVED = '🛠️ Update: Your problem report "{title}" has been marked as resolved.'
MSG_USER_PROBLEM_RESOLVED_WITH_NOTE = (
    '🛠️ Update: Your problem report "{title}" has been marked as resolved by the admin.'
)
MSG_USER_REJECTED_INFO = "❌ Access to this bot has not been granted to your account."
MSG_USER_REJECTED_NOTIFICATION = (
    "🙁 Your account access request has been reviewed and was not approved at this time. You will not be able to use"
    " this bot."
)
MSG_USER_REQUEST_APPROVED = 'Great news! 🎉 Your request for "{title}" has been approved.'
MSG_USER_REQUEST_APPROVED_WITH_NOTE = 'Great news! 🎉 Your request for "{title}" has been approved by the admin.'
MSG_USER_REQUEST_COMPLETED = '✅ Update: Your request for "{title}" is now completed and available!'
MSG_USER_REQUEST_COMPLETED_WITH_NOTE = '✅ Update: Your request for "{title}" has been completed by the admin.'
MSG_USER_REQUEST_DENIED = '📑 Regarding your request for "{title}", the admin has denied it.'
MSG_USER_UNKNOWN_STATUS_INFO = (
    "⚠️ An issue occurred with your account status. Please contact support or try /start again."
)

# PROMPT_ADMIN
PROMPT_ADMIN_ANNOUNCE_TYPE = "📢 Choose announcement type:"
PROMPT_ADMIN_ANNOUNCE_TYPING_MESSAGE = (
    "✍️ Please type your {muted_status} announcement message below. You can cancel from the admin panel if you return"
    " via /start."
)
PROMPT_ADMIN_NOTE_FOR_REQUEST = (
    "✍️ Please send the note for request ID {request_id} to be {base_action_key}d. You can cancel from the admin panel"
    " if you return via /start."
)

# PROMPT_MAIN_MENU
PROMPT_MAIN_MENU_REQUEST_MEDIA = "✍️ What movie or TV show are you looking for? Please type the name below."

# PROMPT_MANUAL_REQUEST
PROMPT_MANUAL_REQUEST = "✍️ Please provide a description for your manual request."
PROMPT_MANUAL_REQUEST_DESCRIPTION = (
    "✍️ Okay, you chose 'Other / Not Found'. Please describe the media you're looking for (e.g., title, year, any"
    ' details). Your original search term was: "{original_query}". This will be sent as a manual request.'
)

# PROMPT_MEDIA
PROMPT_MEDIA_NAME_TYPING = "✍️ Please type the name of the media you're looking for. You can cancel using the main menu."

# PROMPT_PROBLEM_REPORT
PROMPT_PROBLEM_DESCRIPTION = (
    "📝 Please describe the problem you are experiencing below, or use the cancel button in the menu."
)
PROMPT_PROBLEM_DESCRIPTION_RETRY = "✍️ Please type your problem description, or use the cancel button in the menu."

# PROMPT_REQUEST_NOTE
PROMPT_REQUEST_NOTE = "📝 Please send a short note for your request."

# TITLES
TITLE_ADMIN_PANEL = "👑 Admin Panel"
TITLE_ADMIN_TASKS_LIST = "📋 Admin Tasks (Page {page} of {total_pages})"
