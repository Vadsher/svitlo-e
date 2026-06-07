[🇺🇦 Читати інструкцію українською мовою](README.ua.md)

# PingBot 💡

An asynchronous Telegram bot designed to monitor the availability of network hosts (IP addresses or DDNS domain names) using ICMP ping requests. It instantly notifies users about power/network status changes (online/offline) and tracks the exact downtime duration.

> 🤖 **Official Bot:** This repository contains the original source code powering [@custom_svitlo_e_bot](https://t.me/custom_svitlo_e_bot). You can deploy your own version using the instructions below or simply use our pre-hosted bot on Telegram!

## Key Features
- 🖥️ **Interactive UI**: User-friendly menu with "➕ Add address", "📋 My list", and "🗑️ Delete address" buttons for simple management.
- 🛡️ **Robust Validation**: Automatic validation of entered IPv4 addresses and domain names.
- ⏱️ **Flapping Protection**: Notifications about status changes are sent only after a specified number of consecutive successful/failed pings (configured via `STATUS_CHANGE_THRESHOLD`), allowing the bot to ignore brief network drops.
- ⏸️ **Granular Control**: Ability to temporarily pause monitoring for individual hosts, rename them, delete them, or instantly trigger manual status checks.
- 👥 **Group Chats & Admin Roles**: Add the bot to group chats for shared notifications. Only group administrators can configure the bot (add/remove hosts), while all members receive outage notifications.
- 🏘️ **Cluster Monitoring**: Group multiple IP addresses (e.g., neighbors' IPs) into a single logical cluster by separating them with commas. The "Power Off" notification is only triggered if *all* addresses in the cluster are unavailable.
- 🔕 **Quiet Hours**: Configure quiet hours using `/settings` to suppress notifications during the night or other specific times.
- 📊 **Scheduled Outage Reports**: The bot automatically sends daily, weekly, and monthly reports summarizing the number and duration of outages.

## 🚀 Planned Features (Roadmap)
**🌍 Localization**
- Add English localization and bot language selection.

**📋 "My List" Flow Improvements**
- Split the flow depending on the number of saved addresses:
  1) **Multiple addresses**: Show a list of addresses without inline buttons. Clicking an address opens its details with an action menu (Check / Pause / Rename / Delete) and a "Back" button.
  2) **Single address**: Directly show the address details with the action menu.

**📊 Advanced Outage Statistics**
Upcoming updates will introduce a powerful reporting system. Users will be able to view detailed network/power outage statistics for various periods:
- For the current day (24 hours) or the last `n` days
- For the current or previous week
- For the current or previous month
- From a specific date to today (e.g., *from 12/01/2026 to today*)
- For an exact time range (e.g., *from 12/01/2026 to 12/31/2026*)

**⚡ Batch Operations**
- Bulk addition of multiple addresses at once
- Bulk deletion of multiple hosts simultaneously

**🔒 Private Setup Flow**
- Moving administrative FSM steps and group configuration (via `/settings`, `/add`, etc.) to private direct messages with the bot using Deep Linking, preventing configuration commands and inputs from cluttering group chats.

## Tech Stack
- **Python 3.14**
- **aiogram 3.x**
- **PostgreSQL 18.4** (via asyncpg + SQLAlchemy)
- **Alembic** (Database Migrations)
- **icmplib** (Asynchronous, rootless ICMP sockets)
- **Docker & Docker Compose**

## Setup and Deployment

All Docker configurations and environment variables are located in the `.ci-cd` directory.

1. Get a bot token from [@BotFather](https://t.me/BotFather).
2. Create an `.env` file based on the template:
```shell
cp ./.ci-cd/.env.example ./.ci-cd/.env
```

3. Open `.env` and insert your token into the `BOT_TOKEN` variable.

### Database Initialization (First Run)

Since we use Alembic, you need to generate migration files before running the bot for the first time (ensure you are in the root directory of the repository):

1. Start only the database service:
```shell
docker compose -f ./.ci-cd/docker-compose.yml up -d db
```

2. Generate the migration using a temporary bot container (we mount the directory so the file is saved on the host):
```shell
docker compose -f ./.ci-cd/docker-compose.yml run --rm -v ${PWD}/migrations:/app/migrations bot sh -c "alembic -c alembic/alembic.ini revision --autogenerate -m 'Initial setup'"
```
*This will create a migration file in the `migrations/versions/` folder.*

### Deployment

After generating the migrations, bring up all services:
```shell
docker compose -f ./.ci-cd/docker-compose.yml up -d --build
```

The `bot` container will automatically run `alembic upgrade head` before starting the process, check for environment variables, and create all necessary tables.

### Database Management (pgAdmin)

A **pgAdmin** service is spun up alongside the bot and database for convenient database management via a web interface.

1. Open in your browser: `http://localhost:40880`
2. Log in using the credentials specified in your `.env` file:
   - **Email**: `PGADMIN_DEFAULT_EMAIL` value (default: `admin@svitlo.bot`)
   - **Password**: `PGADMIN_DEFAULT_PASSWORD` value (default: `adminpassword`)
3. To connect the PingBot database in pgAdmin:
   - Click **Add New Server**
   - In the **General** tab, enter any name (e.g., *Svitlo DB*)
   - In the **Connection** tab, enter:
     - **Host name/address**: `db` (internal container name)
     - **Port**: `5432`
     - **Maintenance database**: `POSTGRES_DB` value (default: `pingbot`)
     - **Username**: `POSTGRES_USER` value (default: `botuser`)
     - **Password**: `POSTGRES_PASSWORD` value (default: `botpassword`)


## Logging

The bot is configured to output detailed structured logs to `stdout`. To view them (from the root folder), run:
```shell
docker compose -f ./.ci-cd/docker-compose.yml logs -f bot
```

## Testing

The project uses `pytest` for automated testing and a structured checklist for manual QA.

### Manual QA Testing
For step-by-step manual verification of features, refer to the [🧪 QA Testing Guide](QA_Checklist.md). This guide covers user flows, spam protection, quiet hours, and report scheduling.

### Automated Testing
To run the tests locally inside an isolated `python:3.14-slim` container (the exact same way it runs in CI/CD), execute the following command from the repository root:

```shell
docker run --rm -v "${PWD}:/app" -w /app python:3.14-slim sh -c "pip install pipenv && pipenv install --dev && pipenv run pytest --cov=src tests -v"
```

### Test Coverage: 80%
Test coverage is measured using `pytest-cov`. Below is the current breakdown per module:

| Module | Statements | Missed | Coverage |
|---|---|---|---|
| `src/config.py` | 14 | 4 | **71%** |
| `src/database.py` | 34 | 0 | **100%** |
| `src/filters.py` | 10 | 2 | **80%** |
| `src/handlers/__init__.py` | 10 | 0 | **100%** |
| `src/handlers/common.py` | 28 | 1 | **96%** |
| `src/handlers/host_add.py` | 77 | 5 | **94%** |
| `src/handlers/host_list.py` | 209 | 40 | **81%** |
| `src/handlers/settings.py` | 138 | 33 | **76%** |
| `src/handlers/utils.py` | 41 | 19 | **54%** |
| `src/logger.py` | 13 | 0 | **100%** |
| `src/main.py` | 25 | 25 | **0%** |
| `src/monitor.py` | 99 | 18 | **82%** |
| `src/scheduler.py` | 65 | 9 | **86%** |
| **TOTAL** | **763** | **156** | **80%** |

The tests now comprehensively cover DB model CRUD, address validation FSM steps, ping logic helpers, monitoring workflows, scheduling events, and all major user interaction flows inside the handlers module.
