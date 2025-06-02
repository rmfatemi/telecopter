import os

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


ADMIN_GROUP_CHAT_ID: int = int(os.environ.get("ADMIN_GROUP_CHAT_ID", "0"))
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")


TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL: str = "https://image.tmdb.org/t/p/w500"
TMDB_API_KEY: str = os.environ.get("TMDB_API_KEY", "")
TMDB_REQUEST_DISAMBIGUATION_LIMIT: int = int(os.environ.get("TMDB_REQUEST_DISAMBIGUATION_LIMIT", "3"))


TMDB_TV_URL_BASE = "https://www.themoviedb.org/tv/"
IMDB_TITLE_URL_BASE = "https://www.imdb.com/title/"
TMDB_MOVIE_URL_BASE = "https://www.themoviedb.org/movie/"


DATABASE_FILE_PATH: str = os.environ.get("DATABASE_FILE_PATH", "data/telecopter.db")


DEFAULT_PAGE_SIZE: int = int(os.environ.get("DEFAULT_PAGE_SIZE", "5"))
MAX_NOTE_LENGTH: int = int(os.environ.get("MAX_NOTE_LENGTH", "1000"))
MAX_REPORT_LENGTH: int = int(os.environ.get("MAX_REPORT_LENGTH", "2000"))


DATA_DIR = Path(DATABASE_FILE_PATH).parent
