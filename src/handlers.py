"""Telegram bot handlers and callback processing."""
import logging
import re
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.future import select

from src.database import AsyncSessionLocal, Host
from src.monitor import check_host

logger = logging.getLogger(__name__)
router = Router()


# ── FSM State Groups ──────────────────────────────────────────────────────────

class AddHostState(StatesGroup):
    """FSM states for the multi-step add-host workflow."""
    waiting_for_address = State()
    waiting_for_name = State()

class RenameState(StatesGroup):
    """FSM states for renaming a host."""
    waiting_for_name = State()
    host_id = State()


# ── Keyboards ─────────────────────────────────────────────────────────────────

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom-bar keyboard shown in normal (non-FSM) mode."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Додати адресу"), KeyboardButton(text="📋 Мій список")],
            [KeyboardButton(text="🗑️ Видалити адресу")],
        ],
        resize_keyboard=True,
    )

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Bottom-bar keyboard shown during an active workflow."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True,
    )

def get_host_keyboard(host_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Generate inline keyboard for host management."""
    buttons = [
        [InlineKeyboardButton(text="🔍 Перевірити", callback_data=f"check_{host_id}")],
        [InlineKeyboardButton(text="⏸ Пауза" if is_active else "▶️ Продовжити", callback_data=f"toggle_{host_id}")],
        [InlineKeyboardButton(text="✏️ Перейменувати", callback_data=f"rename_{host_id}")],
        [InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"delete_confirm_{host_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_delete_confirm_keyboard(host_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard asking the user to confirm or cancel deletion."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Так, видалити", callback_data=f"delete_execute_{host_id}"),
            InlineKeyboardButton(text="↩️ Назад", callback_data=f"delete_cancel_{host_id}"),
        ]
    ])


# ── Address Validation ────────────────────────────────────────────────────────

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


# ── Global Cancel Handler ─────────────────────────────────────────────────────

@router.message(F.text == "❌ Скасувати")
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel any active workflow and return to the main menu."""
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer("❌ Операцію скасовано.", reply_markup=get_main_menu_keyboard())
    else:
        await message.answer("Немає активної операції.", reply_markup=get_main_menu_keyboard())


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    logger.info(f"User {message.from_user.id} executed /start")
    await state.clear()
    await message.answer(
        "👋 Привіт! Я бот для моніторингу світла та інтернету.\n\n"
        "Використовуй кнопки нижче або команди:\n"
        "• /add - додати адресу для моніторингу\n"
        "• /list - переглянути список адрес\n"
        "• /delete - видалити адресу з моніторингу",
        reply_markup=get_main_menu_keyboard(),
    )


# ── Add Host Workflow ─────────────────────────────────────────────────────────

async def _start_add_flow(message: Message, state: FSMContext) -> None:
    """Shared entry point for the add-host FSM (button or /add command)."""
    await state.set_state(AddHostState.waiting_for_address)
    await message.answer(
        "📡 Введіть IPv4-адресу або доменне ім'я для моніторингу:\n\n"
        "_Приклад: `8.8.8.8` або `example.com`_",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard(),
    )

@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    """Handle /add command - starts the multi-step add workflow."""
    await _start_add_flow(message, state)

@router.message(F.text == "➕ Додати адресу")
async def btn_add(message: Message, state: FSMContext):
    """Handle 'Add address' reply keyboard button."""
    await _start_add_flow(message, state)


@router.message(AddHostState.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    """Validate entered address and ask for a friendly name."""
    address = message.text.strip()

    if not is_valid_address(address):
        await message.answer(
            "⚠️ Невірний формат адреси.\n\n"
            "Будь ласка, введіть коректну *IPv4-адресу* або *доменне ім'я*.\n"
            "_Приклад: `8.8.8.8` або `example.com`_",
            parse_mode="Markdown",
        )
        return  # stay in the same state, re-prompt

    await state.update_data(address=address)
    await state.set_state(AddHostState.waiting_for_name)
    await message.answer(
        f"✅ Адресу `{address}` прийнято!\n\n"
        f"Тепер введіть зручну назву для цього хоста.\n"
        f"_Якщо залишити порожнім - адреса буде використана як назва._",
        parse_mode="Markdown",
    )


@router.message(AddHostState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Save the host with the chosen (or default) name."""
    data = await state.get_data()
    address = data["address"]
    pretty_name = (message.text.strip() or address)[:50]

    async with AsyncSessionLocal() as session:
        new_host = Host(user_id=message.from_user.id, address=address, pretty_name=pretty_name)
        session.add(new_host)
        await session.commit()

    logger.info(f"User {message.from_user.id} added host: {address} as '{pretty_name}'")
    await state.clear()
    await message.answer(
        f"✅ Додано: *{pretty_name}* (`{address}`)\nМоніторинг розпочато!",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


# ── /list ─────────────────────────────────────────────────────────────────────

@router.message(Command("list"))
async def cmd_list(message: Message):
    """Handle /list command."""
    await _show_list(message)

@router.message(F.text == "📋 Мій список")
async def btn_list(message: Message):
    """Handle 'My list' reply keyboard button."""
    await _show_list(message)

async def _show_list(message: Message) -> None:
    """Query and display all hosts for the user."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Host).where(Host.user_id == message.from_user.id))
        hosts = result.scalars().all()

        if not hosts:
            await message.answer(
                "📭 У вас немає доданих адрес.\n\nДодайте першу за допомогою кнопки нижче.",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        for h in hosts:
            status = "🟢 Світло є" if h.status_up else "🔴 Світло вимкнено"
            paused = " (ПАУЗА)" if not h.is_active else ""
            text = f"🖥 *{h.pretty_name}* (`{h.address}`)\nСтатус: {status}{paused}"
            await message.answer(text, parse_mode="Markdown", reply_markup=get_host_keyboard(h.id, h.is_active))


# ── Inline Callbacks ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("check_"))
async def callback_check(callback: CallbackQuery):
    """Handle manual check request via inline button."""
    host_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host:
            return await callback.answer("Хост не знайдено", show_alert=True)

        await callback.answer(f"Перевіряю {host.pretty_name}...", show_alert=False)
        is_up = await check_host(host.address)
        status = "🟢 Світло є" if is_up else "🔴 Світло вимкнено"
        logger.info(f"Manual check for {host.address}: {'UP' if is_up else 'DOWN'}")
        await callback.message.reply(
            f"Поточний статус *{host.pretty_name}*: {status}", parse_mode="Markdown"
        )

@router.callback_query(F.data.startswith("toggle_"))
async def callback_toggle(callback: CallbackQuery):
    """Handle pause/resume request via inline button."""
    host_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if host:
            host.is_active = not host.is_active
            await session.commit()
            action = "відновлено" if host.is_active else "призупинено"
            logger.info(f"Monitoring for {host.address} {'resumed' if host.is_active else 'paused'}")
            await callback.message.edit_reply_markup(reply_markup=get_host_keyboard(host.id, host.is_active))
            await callback.answer(f"Моніторинг {host.pretty_name} {action}")

@router.callback_query(F.data.startswith("rename_"))
async def callback_rename(callback: CallbackQuery, state: FSMContext):
    """Initiate rename process via inline button."""
    host_id = int(callback.data.split("_")[1])
    
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host:
            return await callback.answer("Хост не знайдено", show_alert=True)
        current_name = host.pretty_name

    await state.update_data(host_id=host_id)
    await state.set_state(RenameState.waiting_for_name)
    await callback.message.answer(
        f"✏️ Введіть нову назву для хоста *{current_name}*:", 
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(RenameState.waiting_for_name)
async def process_new_name(message: Message, state: FSMContext):
    """Process the text input for the new host name."""
    data = await state.get_data()
    host_id = data.get("host_id")

    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if host:
            old_name = host.pretty_name
            host.pretty_name = message.text[:50]
            await session.commit()
            logger.info(f"Host {host.address} renamed from '{old_name}' to '{host.pretty_name}'")
            await message.answer(
                f"✅ Назву змінено: *{old_name}* → *{host.pretty_name}*",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
            )

    await state.clear()


# ── Delete Host ───────────────────────────────────────────────────────────────

async def _show_delete_list(message: Message) -> None:
    """Show all hosts with a prompt to tap 🗑️ on the one to remove."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Host).where(Host.user_id == message.from_user.id))
        hosts = result.scalars().all()

        if not hosts:
            await message.answer(
                "📭 У вас немає доданих адрес.",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        await message.answer(
            "🗑️ Оберіть адресу для видалення, натиснувши *Видалити* під потрібним хостом:",
            parse_mode="Markdown",
        )
        for h in hosts:
            status = "🟢 Світло є" if h.status_up else "🔴 Світло вимкнено"
            text = f"🖥 *{h.pretty_name}* (`{h.address}`)\nСтатус: {status}"
            await message.answer(text, parse_mode="Markdown", reply_markup=get_host_keyboard(h.id, h.is_active))

@router.message(Command("delete"))
async def cmd_delete(message: Message):
    """Handle /delete command - shows host list for selection."""
    await _show_delete_list(message)

@router.message(F.text == "🗑️ Видалити адресу")
async def btn_delete(message: Message):
    """Handle 'Delete address' reply keyboard button."""
    await _show_delete_list(message)

@router.callback_query(F.data.startswith("delete_confirm_"))
async def callback_delete_confirm(callback: CallbackQuery):
    """Replace host keyboard with a confirmation prompt."""
    host_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host:
            return await callback.answer("Хост не знайдено", show_alert=True)

    await callback.message.edit_text(
        f"❓ Ви дійсно хочете видалити хост *{host.pretty_name}* (`{host.address}`)?\nЦю дію неможливо скасувати.",
        parse_mode="Markdown",
        reply_markup=get_delete_confirm_keyboard(host_id),
    )
    await callback.answer()

@router.callback_query(F.data.startswith("delete_execute_"))
async def callback_delete_execute(callback: CallbackQuery):
    """Delete the host from the database after user confirmation."""
    host_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host:
            return await callback.answer("Хост не знайдено", show_alert=True)

        name = host.pretty_name
        address = host.address
        await session.delete(host)
        await session.commit()

    logger.info(f"User {callback.from_user.id} deleted host: {address}")
    await callback.message.edit_text(
        f"🗑️ *{name}* (`{address}`) видалено.", parse_mode="Markdown"
    )
    await callback.answer("Видалено")

@router.callback_query(F.data.startswith("delete_cancel_"))
async def callback_delete_cancel(callback: CallbackQuery):
    """Cancel deletion and restore the original host keyboard."""
    host_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host:
            return await callback.answer()

    await callback.message.edit_reply_markup(
        reply_markup=get_host_keyboard(host_id, host.is_active)
    )
    await callback.answer("Скасовано")
