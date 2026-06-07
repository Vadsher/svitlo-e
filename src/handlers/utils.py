import time
import re
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, CallbackQuery

from src.filters import IsAdminFilter

user_callback_cache = {}

async def check_is_admin(message_or_callback) -> bool:
    """Helper to check if user is admin programmatically."""
    filter_obj = IsAdminFilter()
    return await filter_obj(message_or_callback)

async def check_callback_debounce(user_id: int) -> int:
    """Returns wait time in seconds if debounced, else 0. Progressively increases."""
    now = time.time()
    if user_id in user_callback_cache:
        last_time, wait_time = user_callback_cache[user_id]
        if now - last_time < wait_time:
            # Still in cooldown, increase next cooldown exponentially (up to 60s)
            new_wait = min(wait_time * 2, 60)
            user_callback_cache[user_id] = (last_time, new_wait)
            return int(wait_time - (now - last_time))
        else:
            # Cooldown passed, reset
            user_callback_cache[user_id] = (now, 5)
            return 0
    else:
        user_callback_cache[user_id] = (now, 5)
        return 0

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom-bar keyboard shown in normal (non-FSM) mode."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Додати адресу"), KeyboardButton(text="📋 Мій список")],
            [KeyboardButton(text="⚙️ Налаштування"), KeyboardButton(text="🗑️ Видалити адресу")],
        ],
        resize_keyboard=True,
    )

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Bottom-bar keyboard shown during an active workflow."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True,
    )

def is_valid_ipv4(value: str) -> bool:
    """Validate an IPv4 address."""
    match = re.match(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$', value)
    return bool(match) and all(0 <= int(g) <= 255 for g in match.groups())

def is_valid_domain(value: str) -> bool:
    """Validate a domain name."""
    pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    return bool(re.match(pattern, value))

def is_valid_address(value: str) -> bool:
    """Return True if the value is a valid IPv4 address or domain name."""
    return is_valid_ipv4(value) or is_valid_domain(value)

async def verify_callback_admin_and_debounce(callback: CallbackQuery) -> bool:
    """Verify admin status and debouncing for inline buttons."""
    if not await check_is_admin(callback):
        await callback.answer("⛔ Тільки адміністратори можуть керувати налаштуваннями.", show_alert=True)
        return False
        
    wait_time = await check_callback_debounce(callback.from_user.id)
    if wait_time > 0:
        await callback.answer(f"⏳ Зачекайте {wait_time} с...", show_alert=False)
        return False
        
    return True
