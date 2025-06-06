import datetime
import aiosqlite

from pathlib import Path
from typing import Optional, List

from telecopter.logger import setup_logger
from telecopter.constants import UserStatus, RequestStatus
from telecopter.config import DATABASE_FILE_PATH, DEFAULT_PAGE_SIZE


logger = setup_logger(__name__)


async def initialize_database():
    db_path = Path(DATABASE_FILE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        await db.execute(f"""
            create table if not exists users (
                user_id integer primary key,
                chat_id integer unique not null,
                username text,
                first_name text,
                approval_status text not null default '{UserStatus.NEW.value}',
                created_at text not null default current_timestamp,
                last_active_at text not null default current_timestamp
            )
        """)
        logger.info("users table initialized.")

        await db.execute("""
                            create table if not exists requests
                            (
                                request_id  integer primary key autoincrement,
                                user_id     integer not null,
                                request_type text   not null,
                                status      text   not null,
                                tmdb_id     integer,
                                title       text   not null,
                                year        integer,
                                imdb_id     text,
                                user_query  text,
                                user_note   text,
                                admin_note  text,
                                created_at  text   not null default current_timestamp,
                                updated_at  text   not null default current_timestamp,
                                foreign key (user_id) references users (user_id)
                            )
                            """)
        logger.info("requests table initialized.")

        await db.execute("""
                            create trigger if not exists update_requests_updated_at
                                after update
                                on requests
                                for each row
                            begin
                                update requests set updated_at = current_timestamp where request_id = old.request_id;
                            end;
                            """)
        logger.info("requests table 'updated_at' trigger initialized.")

        await db.execute("""
                            create table if not exists admin_logs
                            (
                                log_id      integer primary key autoincrement,
                                admin_user_id integer not null,
                                request_id  integer,
                                action      text   not null,
                                details     text,
                                created_at  text   not null default current_timestamp,
                                foreign key (request_id) references requests (request_id),
                                foreign key (admin_user_id) references users (user_id)
                            )
                            """)
        logger.info("admin_logs table initialized.")
        await db.commit()
    logger.info("database initialization complete.")


async def add_or_update_user(
    user_id: int, chat_id: int, username: str | None, first_name: str | None, is_admin_user: bool = False
):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        async with db.execute("select approval_status from users where user_id = ?", (user_id,)) as cursor:
            existing_user_row = await cursor.fetchone()

        if existing_user_row:
            await db.execute(
                """
                update users
                set chat_id        = ?,
                    username       = ?,
                    first_name     = ?,
                    last_active_at = ?
                where user_id = ?
                """,
                (chat_id, username, first_name, now, user_id),
            )
        else:
            initial_approval_status = UserStatus.APPROVED.value if is_admin_user else UserStatus.NEW.value
            await db.execute(
                """
                insert into users (user_id, chat_id, username, first_name, approval_status, created_at, last_active_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, chat_id, username, first_name, initial_approval_status, now, now),
            )
        await db.commit()
        logger.debug(
            "user %s (chat_id: %s) added or updated. admin_flag: %s, new_user: %s",
            user_id,
            chat_id,
            is_admin_user,
            not existing_user_row,
        )


async def get_user(user_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("select * from users where user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def get_user_approval_status(user_id: int) -> Optional[str]:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        async with db.execute("select approval_status from users where user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def update_user_approval_status(user_id: int, new_status: str) -> bool:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        cursor = await db.execute(
            "update users set approval_status = ?, last_active_at = ? where user_id = ?",
            (new_status, now, user_id),
        )
        await db.commit()
        if cursor.rowcount > 0:
            logger.info("user %s approval_status updated to %s.", user_id, new_status)
            return True
        logger.warning("failed to update approval_status for user %s. user not found or no change.", user_id)
        return False


async def get_pending_approval_users(page: int, page_size: int = DEFAULT_PAGE_SIZE) -> List[aiosqlite.Row]:
    offset = (page - 1) * page_size
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "select * from users where approval_status = ? order by created_at asc limit ? offset ?",
            (UserStatus.PENDING_APPROVAL.value, page_size, offset),
        ) as cursor:
            return await cursor.fetchall()


async def get_pending_approval_users_count() -> int:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        async with db.execute(
            "select count(*) from users where approval_status = ?", (UserStatus.PENDING_APPROVAL.value,)
        ) as cursor:
            total_row = await cursor.fetchone()
            return total_row[0] if total_row else 0


async def add_request(
    user_id: int,
    request_type: str,
    title: str,
    status: str = RequestStatus.PENDING_ADMIN.value,  # Changed this line
    tmdb_id: Optional[int] = None,
    year: Optional[int] = None,
    imdb_id: Optional[str] = None,
    user_query: Optional[str] = None,
    user_note: Optional[str] = None,
) -> int:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        cursor = await db.execute(
            """
            insert into requests (user_id, request_type, status, tmdb_id, title, year, imdb_id, user_query, user_note,
                                    created_at, updated_at)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                request_type,
                status,
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
        if request_id is None:
            logger.error("failed to retrieve lastrowid after request insertion for type %s.", request_type)
            raise DatabaseError(f"failed to retrieve lastrowid for request type {request_type}")
        logger.info(
            "%s request added. request_id: %s, user_id: %s, title: %s",
            request_type,
            request_id,
            user_id,
            title,
        )
        return request_id


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
    return await add_request(
        user_id=user_id,
        request_type=request_type,
        title=title,
        tmdb_id=tmdb_id,
        year=year,
        imdb_id=imdb_id,
        user_query=user_query,
        user_note=user_note,
    )


async def add_problem_report(user_id: int, problem_description: str, user_note: str | None = None) -> int:
    return await add_request(user_id=user_id, request_type="problem", title=problem_description, user_note=user_note)


async def get_user_requests(user_id: int, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> list[aiosqlite.Row]:
    offset = (page - 1) * page_size
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            select *
            from requests
            where user_id = ?
            order by created_at desc
            limit ? offset ?
            """,
            (user_id, page_size, offset),
        ) as cursor:
            return await cursor.fetchall()


async def get_user_requests_count(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        async with db.execute("select count(*) from requests where user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result and result[0] is not None else 0


async def get_request_by_id(request_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("select * from requests where request_id = ?", (request_id,)) as cursor:
            return await cursor.fetchone()


async def update_request_status(request_id: int, new_status: str, admin_note: str | None = None) -> bool:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        if admin_note is not None:
            cursor = await db.execute(
                "update requests set status = ?, admin_note = ?, updated_at = ? where request_id = ?",
                (new_status, admin_note, now, request_id),
            )
        else:
            cursor = await db.execute(
                "update requests set status = ?, updated_at = ? where request_id = ?",
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
            insert into admin_logs (admin_user_id, request_id, action, details, created_at)
            values (?, ?, ?, ?, ?)
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
        async with db.execute("select distinct chat_id from users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_request_submitter_chat_id(request_id: int) -> int | None:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as db:
        query = """
                    select u.chat_id
                    from requests r
                            join users u on r.user_id = u.user_id
                    where r.request_id = ?
                    """
        async with db.execute(query, (request_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def get_actionable_admin_requests(page: int, page_size: int = DEFAULT_PAGE_SIZE) -> List[aiosqlite.Row]:
    offset = (page - 1) * page_size
    async with aiosqlite.connect(DATABASE_FILE_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        query = f"""
                    select * from requests
                    where status = '{RequestStatus.PENDING_ADMIN.value}'
                       or status = '{RequestStatus.APPROVED.value}'
                    order by case status
                                 when '{RequestStatus.PENDING_ADMIN.value}' then 1
                                 when '{RequestStatus.APPROVED.value}' then 2
                                 else 3
                             end,
                             created_at asc
                    limit ? offset ?
                    """
        cursor = await conn.execute(query, (page_size, offset))
        return await cursor.fetchall()


async def get_actionable_admin_requests_count() -> int:
    async with aiosqlite.connect(DATABASE_FILE_PATH) as conn:
        cursor = await conn.execute(
            f"select count(*) from requests where status = '{RequestStatus.PENDING_ADMIN.value}' or status ="
            f" '{RequestStatus.APPROVED.value}'"
        )
        result = await cursor.fetchone()
        return result[0] if result and result[0] is not None else 0


class DatabaseError(Exception):
    pass
