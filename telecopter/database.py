import datetime
import aiosqlite

from pathlib import Path
from typing import Optional

from telecopter.logger import setup_logger
from telecopter.config import DATABASE_FILE_PATH


logger = setup_logger(__name__)


async def initialize_database():
    db_path = Path(DATABASE_FILE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_active_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)
        logger.info("users table initialized.")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                request_type TEXT NOT NULL,
                status TEXT NOT NULL,
                tmdb_id INTEGER,
                title TEXT NOT NULL,
                year INTEGER,
                imdb_id TEXT,
                user_query TEXT,
                user_note TEXT,
                admin_note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """)
        logger.info("requests table initialized.")

        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS update_requests_updated_at
            AFTER UPDATE ON requests
            FOR EACH ROW
            BEGIN
                UPDATE requests SET updated_at = CURRENT_TIMESTAMP WHERE request_id = OLD.request_id;
            END;
            """)
        logger.info("requests table 'updated_at' trigger initialized.")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_user_id INTEGER NOT NULL,
                request_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES requests(request_id),
                FOREIGN KEY (admin_user_id) REFERENCES users(user_id)
            )
            """)
        logger.info("admin_logs table initialized.")
        await db.commit()
    logger.info("database initialization complete.")


async def add_or_update_user(user_id: int, chat_id: int, username: str | None, first_name: str | None):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, chat_id, username, first_name, created_at, last_active_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                username = excluded.username,
                first_name = excluded.first_name,
                last_active_at = excluded.last_active_at
            """,
            (user_id, chat_id, username, first_name, now, now),
        )
        await db.commit()
        logger.debug("user %s (chat_id: %s) added or updated.", user_id, chat_id)


async def get_user(user_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def add_media_request(
    user_id: int,
    tmdb_id: Optional[int],
    title: str,
    year: int | None,
    imdb_id: str | None,
    request_type: str,
    user_query: str | None,
    user_note: str | None,
) -> int:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO requests (user_id, request_type, status, tmdb_id, title, year, imdb_id, user_query, user_note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                request_type,
                "pending_admin",
                tmdb_id,
                title,
                year,
                imdb_id,
                user_query,
                user_note,
                now,
                now,
            ),
        )
        await db.commit()
        request_id = cursor.lastrowid
        logger.info(
            "media request added. request_id: %s, user_id: %s, tmdb_id: %s, title: %s, type: %s",
            request_id,
            user_id,
            tmdb_id if tmdb_id is not None else "none",
            title,
            request_type,
        )
        return request_id


async def add_problem_report(user_id: int, problem_description: str, user_note: str | None = None) -> int:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO requests (user_id, request_type, status, title, user_note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                "problem",
                "pending_admin",
                problem_description,
                user_note,
                now,
                now,
            ),
        )
        await db.commit()
        request_id = cursor.lastrowid
        logger.info(
            "problem report added. request_id: %s, user_id: %s, description: %s",
            request_id,
            user_id,
            problem_description[:50],
        )
        return request_id


async def get_user_requests(user_id: int, page: int = 1, page_size: int = 5) -> list[aiosqlite.Row]:
    offset = (page - 1) * page_size
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM requests
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, page_size, offset),
        ) as cursor:
            return await cursor.fetchall()


async def get_user_requests_count(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM requests WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0


async def get_request_by_id(request_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,)) as cursor:
            return await cursor.fetchone()


async def update_request_status(request_id: int, new_status: str, admin_note: str | None = None) -> bool:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        if admin_note is not None:
            cursor = await db.execute(
                "UPDATE requests SET status = ?, admin_note = ?, updated_at = ? WHERE request_id = ?",
                (new_status, admin_note, now, request_id),
            )
        else:
            cursor = await db.execute(
                "UPDATE requests SET status = ?, updated_at = ? WHERE request_id = ?",
                (new_status, now, request_id),
            )
        await db.commit()
        updated_rows = cursor.rowcount
        if updated_rows > 0:
            logger.info("request %s status updated to %s.", request_id, new_status)
            return True
        logger.warning("failed to update status for request %s. request not found or no change.", request_id)
        return False


async def log_admin_action(admin_user_id: int, action: str, details: str | None = None, request_id: int | None = None):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        await db.execute(
            """
            INSERT INTO admin_logs (admin_user_id, request_id, action, details, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (admin_user_id, request_id, action, details, now),
        )
        await db.commit()
        logger.info(
            "admin action logged. admin_id: %s, action: %s, request_id: %s",
            admin_user_id,
            action,
            request_id if request_id else "n/a",
        )


async def get_all_user_chat_ids() -> list[int]:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        async with db.execute("SELECT DISTINCT chat_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_request_submitter_chat_id(request_id: int) -> int | None:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        query = """
        SELECT u.chat_id
        FROM requests r
        JOIN users u ON r.user_id = u.user_id
        WHERE r.request_id = ?
        """
        async with db.execute(query, (request_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
