import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID_STR: str = os.environ.get("ADMIN_CHAT_ID", "")

ADMIN_CHAT_ID: int = 0
if ADMIN_CHAT_ID_STR.isdigit():
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_STR)
else:
    if ADMIN_CHAT_ID_STR:
        print(f"warning: admin_chat_id '{ADMIN_CHAT_ID_STR}' is not a valid integer. admin features may not work.")

TMDB_API_KEY: str = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL: str = "https://image.tmdb.org/t/p/w500"
TMDB_REQUEST_DISAMBIGUATION_LIMIT: int = int(os.environ.get("TMDB_REQUEST_DISAMBIGUATION_LIMIT", "3"))

DATABASE_FILE_PATH: str = os.environ.get("DATABASE_FILE_PATH", "data/telecopter.db")

DEFAULT_PAGE_SIZE: int = int(os.environ.get("DEFAULT_PAGE_SIZE", "5"))
MAX_NOTE_LENGTH: int = int(os.environ.get("MAX_NOTE_LENGTH", "1000"))
MAX_REPORT_LENGTH: int = int(os.environ.get("MAX_REPORT_LENGTH", "2000"))

DATA_DIR = os.path.dirname(DATABASE_FILE_PATH)
if DATA_DIR and not os.path.exists(DATA_DIR):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except OSError as e:
        print(f"error: could not create data directory at {DATA_DIR}: {e}")

if not TELEGRAM_BOT_TOKEN:
    print("critical_error: telegram_bot_token not found in environment variables. bot cannot start.")

if not ADMIN_CHAT_ID:
    print("warning: admin_chat_id not set or invalid. admin features will not work correctly.")

if not TMDB_API_KEY:
    print("warning: tmdb_api_key not found. media search functionality will be disabled.")
