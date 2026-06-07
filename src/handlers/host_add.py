import logging
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.future import select
from sqlalchemy import func

from src.database import AsyncSessionLocal, Host
from src.filters import IsAdminFilter
from src.config import STATUS_CHANGE_THRESHOLD
from src.handlers.utils import get_main_menu_keyboard, get_cancel_keyboard, is_valid_address

logger = logging.getLogger(__name__)
router = Router()

MAX_HOSTS_PER_CHAT = 10

class AddHostState(StatesGroup):
    """FSM states for the multi-step add-host workflow."""
    waiting_for_address = State()
    waiting_for_name = State()
    waiting_for_threshold = State()

async def _start_add_flow(message: Message, state: FSMContext) -> None:
    """Shared entry point for the add-host FSM (button or /add command)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count(Host.id)).where(Host.user_id == message.chat.id))
        count = result.scalar() or 0
        if count >= MAX_HOSTS_PER_CHAT:
            await message.answer(f"⛔ Досягнуто ліміт хостів ({MAX_HOSTS_PER_CHAT}) для цього чату.")
            return

    await state.set_state(AddHostState.waiting_for_address)
    await message.answer(
        "📡 Введіть IPv4-адресу або доменне ім'я для моніторингу (можна кілька через кому для комплексного моніторингу):\n\n"
        "_Приклад: `8.8.8.8, 1.1.1.1` або `example.com`_",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard(),
    )

@router.message(Command("add"), IsAdminFilter())
async def cmd_add(message: Message, state: FSMContext):
    """Handle /add command - starts the multi-step add workflow."""
    await _start_add_flow(message, state)

@router.message(F.text == "➕ Додати адресу", IsAdminFilter())
async def btn_add(message: Message, state: FSMContext):
    """Handle 'Add address' reply keyboard button."""
    await _start_add_flow(message, state)

@router.message(AddHostState.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    """Validate entered address and ask for a friendly name."""
    address = message.text.strip()
    
    # Simple validation for comma-separated list
    addresses = [a.strip() for a in address.split(',')]
    valid = all(is_valid_address(a) for a in addresses if a)
    
    if not valid or not addresses:
        await message.answer(
            "⚠️ Невірний формат адреси.\n\n"
            "Будь ласка, введіть коректні *IPv4-адреси* або *доменні імена* через кому.\n"
            "_Приклад: `8.8.8.8` або `example.com`_",
            parse_mode="Markdown",
        )
        return

    await state.update_data(address=address)
    await state.set_state(AddHostState.waiting_for_name)
    await message.answer(
        f"✅ Адресу `{address}` прийнято!\n\n"
        f"Тепер введіть зручну назву для цього хоста/кластера.\n"
        f"_Якщо залишити порожнім - адреса буде використана як назва._",
        parse_mode="Markdown",
    )

@router.message(AddHostState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Save the name and ask for threshold."""
    data = await state.get_data()
    address = data["address"]
    pretty_name = (message.text.strip() or address)[:50]
    await state.update_data(pretty_name=pretty_name)

    await state.set_state(AddHostState.waiting_for_threshold)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"⏭️ Пропустити (За замовчуванням: {STATUS_CHANGE_THRESHOLD})")],
            [KeyboardButton(text="❌ Скасувати")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        f"⏳ Напишіть індивідуальну чутливість (від 1 до 10 невдалих пінгів) для `{pretty_name}`,\n"
        f"або натисніть 'Пропустити' для використання значення за замовчуванням ({STATUS_CHANGE_THRESHOLD}).",
        reply_markup=keyboard,
    )

@router.message(AddHostState.waiting_for_threshold)
async def process_threshold(message: Message, state: FSMContext):
    """Save the host with the chosen threshold."""
    data = await state.get_data()
    address = data["address"]
    pretty_name = data["pretty_name"]
    
    threshold = None
    if not message.text.startswith("⏭️"):
        try:
            val = int(message.text.strip())
            if 1 <= val <= 10:
                threshold = val
            else:
                await message.answer("⚠️ Введіть число від 1 до 10, або натисніть 'Пропустити'.")
                return
        except ValueError:
            await message.answer("⚠️ Введіть коректне число від 1 до 10, або натисніть 'Пропустити'.")
            return

    async with AsyncSessionLocal() as session:
        new_host = Host(user_id=message.chat.id, address=address, pretty_name=pretty_name, ping_threshold=threshold)
        session.add(new_host)
        await session.commit()

    logger.info(f"User {message.from_user.id} added host: {address} to chat {message.chat.id} as '{pretty_name}'")
    await state.clear()
    await message.answer(
        f"✅ Додано: *{pretty_name}* (`{address}`)\nМоніторинг розпочато!",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )
