"""Application configuration module."""
import os
from zoneinfo import ZoneInfo

# Load and validate Telegram Token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN or BOT_TOKEN == "ТВІЙ_ТЕЛЕГРАМ_ТОКЕН":
    raise ValueError(
        "CRITICAL ERROR: BOT_TOKEN is missing or not configured. "
        "Please check your .env file and ensure a valid Telegram token is provided."
    )

# Load and validate Database URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "CRITICAL ERROR: DATABASE_URL is not set. "
        "Please check your .env file and ensure the database connection string is provided."
    )

# Load and validate Timezone
tz_env = os.getenv("TZ", "Europe/Kyiv")
try:
    KYIV_TZ = ZoneInfo(tz_env)
except Exception as e:
    raise ValueError(
        f"CRITICAL ERROR: Invalid timezone format TZ='{tz_env}'. "
        "Expected format is an IANA time zone like 'Europe/Kyiv'."
    ) from e

# Consecutive ping threshold to confirm status change (prevents false positives)
STATUS_CHANGE_THRESHOLD = int(os.getenv("STATUS_CHANGE_THRESHOLD", "5"))
