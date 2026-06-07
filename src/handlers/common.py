import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.handlers.utils import get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.text == "❌ Скасувати")
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel any active workflow and return to the main menu."""
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer("❌ Операцію скасовано.", reply_markup=get_main_menu_keyboard())
    else:
        await message.answer("Немає активної операції.", reply_markup=get_main_menu_keyboard())

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
        "• /delete - видалити адресу з моніторингу\n"
        "• /help - отримати довідку",
        reply_markup=get_main_menu_keyboard(),
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = (
        "💡 **Доступні команди:**\n\n"
        "🔹 /start - Почати роботу з ботом\n"
        "🔹 /add - Додати новий хост для моніторингу (у групах тільки для адмінів)\n"
        "🔹 /list - Показати список ваших хостів та їх статус\n"
        "🔹 /delete - Видалити хост (у групах тільки для адмінів)\n"
        "🔹 /settings - Налаштувати тихі години та звіти (у групах тільки для адмінів)\n"
        "🔹 /about - Інформація про бота\n"
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.message(Command("about"))
async def cmd_about(message: Message):
    """Handle /about command"""
    about_text = (
        "🤖 **PingBot (Світло Є?)**\n\n"
        "Бот створений для моніторингу доступності мережевого обладнання "
        "(роутерів, серверів) шляхом періодичного пінгування.\n\n"
        "Версія: 1.1\n"
        "Розроблено для відстеження наявності електроенергії/зв'язку."
    )
    await message.answer(about_text, parse_mode="Markdown")
