# Telecopter

Telecopter is an asynchronous Telegram bot designed to streamline media requests. Users can search for movies and TV shows, submit requests, and track their status. Administrators have a dedicated panel to manage incoming requests, approve new users, and broadcast messages.

## ✅ Features

### For Users

  - **Search Media**: Search for movies and TV shows using TMDB's API.
  - **Submit Requests**: Request media with the option to add personal notes.
  - **Manual Requests**: If media isn't found, users can submit a manual request with a description.
  - **Request History**: View a personal history of all submitted requests and their current status (e.g., Pending, Approved, Completed).
  - **Problem Reporting**: Report issues directly to administrators.
  - **Access Control**: New users must request access and be approved by an administrator before they can use the bot.

### For Admins

  - **Admin Panel**: A central dashboard to access all administrative functions.
  - **Task Management**: View a paginated list of all pending requests and problem reports from users.
  - **Request Moderation**: Approve, deny, or mark requests as complete. Admins can also add notes to their actions, which are visible to the user.
  - **User Management**: View a list of users pending approval and approve or reject their access requests.
  - **Broadcast System**: Send custom messages to all approved users of the bot, with options for muted or un-muted notifications.

## ⚙️ Configuration

The application is configured using environment variables. Create a `.env` file in the project root.

```env
# --- Required ---
# Get this from @BotFather on Telegram
TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"

# Comma-separated list of admin Telegram User IDs
ADMIN_CHAT_IDS="12345678,87654321"

# Get this from The Movie Database (TMDB) website
TMDB_API_KEY="YOUR_TMDB_API_KEY"

# --- Optional ---
# Path for the SQLite database file
DATABASE_FILE_PATH="data/telecopter.db"

# Number of items to show per page in paginated lists (e.g., tasks, requests)
DEFAULT_PAGE_SIZE="3"

# Maximum number of search results to show when a user searches for media
TMDB_REQUEST_DISAMBIGUATION_LIMIT="3"

# Maximum character length for user notes and problem reports
MAX_NOTE_LENGTH="1000"
MAX_REPORT_LENGTH="2000"

```

## 🏗️ Setup

### Prerequisites

  - Python 3.11+
  - [Poetry](https://www.google.com/search?q=https://python-poetry.org/docs/%23installation) for dependency management

### Installation & Running

1.  **Clone the repository:**

    ```sh
    git clone https://github.com/your-username/telecopter.git
    cd telecopter
    ```

2.  **Install dependencies:**
    Poetry will create a virtual environment and install all necessary packages.

    ```sh
    poetry install
    ```

3.  **Set up your configuration:**
    Create a `.env` file in the project's root directory and populate it with the required tokens and IDs as described in the [Configuration](https://www.google.com/search?q=%23%EF%B8%8F-configuration) section.

4.  **Run the bot:**
    Execute the bot using the poetry script defined in `pyproject.toml`.

    ```sh
    poetry run telecopter
    ```

    The bot will start polling for updates.


## 🔑 License

This project is licensed under the  GPL-3.0 license - see the [LICENSE](https://github.com/rmfatemi/telecopter/blob/master/LICENSE) file for details.
