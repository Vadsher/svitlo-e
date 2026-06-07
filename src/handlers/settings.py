import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.future import select

from src.database import AsyncSessionLocal, ChatSettings
from src.filters import IsAdminFilter
from src.handlers.utils import verify_callback_admin_and_debounce, get_cancel_keyboard, get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()

class SettingsTimeState(StatesGroup):
    waiting_for_quiet_hours = State()
    waiting_for_report_time = State()
    waiting_for_timezone = State()

async def get_settings(chat_id: int) -> ChatSettings:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ChatSettings).where(ChatSettings.chat_id == chat_id))
        settings = result.scalars().first()
        if not settings:
            settings = ChatSettings(chat_id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings

def get_settings_keyboard(settings: ChatSettings) -> InlineKeyboardMarkup:
    qh = f"{settings.quiet_hours_start.strftime('%H:%M')}-{settings.quiet_hours_end.strftime('%H:%M')}" if settings.quiet_hours_start else "Вимкнено"
    rep_en = "Увімкнено" if settings.report_enabled else "Вимкнено"
    rep_time = settings.report_time.strftime('%H:%M') if settings.report_time else "21:00"
    skip_empty = "Пропускати" if settings.report_skip_empty_daily else "Надсилати"
    tz = settings.timezone_name or "Europe/Kyiv"
    
    buttons = [
        [InlineKeyboardButton(text=f"🌙 Тихі години: {qh}", callback_data="set_qh")],
        [InlineKeyboardButton(text=f"📊 Звіти: {rep_en}", callback_data="set_repen")],
        [InlineKeyboardButton(text=f"🕒 Час звітів: {rep_time}", callback_data="set_reptime")],
        [InlineKeyboardButton(text=f"🙈 Порожні щоденні: {skip_empty}", callback_data="set_skipemp")],
        [InlineKeyboardButton(text=f"🌍 Часовий пояс: {tz}", callback_data="set_tz")],
        [InlineKeyboardButton(text="✅ Готово", callback_data="set_done")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("settings"), IsAdminFilter())
@router.message(F.text == "⚙️ Налаштування", IsAdminFilter())
async def cmd_settings(message: Message, state: FSMContext):
    """Show interactive settings menu."""
    await state.clear()
    settings = await get_settings(message.chat.id)
    await message.answer(
        "⚙️ *Налаштування чату*\n\nОберіть параметр для зміни:",
        parse_mode="Markdown",
        reply_markup=get_settings_keyboard(settings)
    )

@router.callback_query(F.data == "set_done")
async def callback_set_done(callback: CallbackQuery):
    if not await verify_callback_admin_and_debounce(callback): return
    await callback.message.delete()
    await callback.answer("Налаштування закрито")

@router.callback_query(F.data == "set_repen")
async def callback_toggle_report(callback: CallbackQuery):
    if not await verify_callback_admin_and_debounce(callback): return
    async with AsyncSessionLocal() as session:
        settings = await get_settings(callback.message.chat.id)
        settings = await session.merge(settings)
        settings.report_enabled = not settings.report_enabled
        await session.commit()
        await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(settings))
    await callback.answer()

@router.callback_query(F.data == "set_skipemp")
async def callback_toggle_skip_empty(callback: CallbackQuery):
    if not await verify_callback_admin_and_debounce(callback): return
    async with AsyncSessionLocal() as session:
        settings = await get_settings(callback.message.chat.id)
        settings = await session.merge(settings)
        settings.report_skip_empty_daily = not settings.report_skip_empty_daily
        await session.commit()
        await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(settings))
    await callback.answer()

@router.callback_query(F.data == "set_qh")
async def callback_set_qh(callback: CallbackQuery, state: FSMContext):
    if not await verify_callback_admin_and_debounce(callback): return
    await state.set_state(SettingsTimeState.waiting_for_quiet_hours)
    await callback.message.answer(
        "🌙 Введіть час початку та закінчення тихих годин у форматі `ГГ:ХХ-ГГ:ХХ` (наприклад `23:00-08:00`), або `0` щоб вимкнути:",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(SettingsTimeState.waiting_for_quiet_hours)
async def process_quiet_hours(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    async with AsyncSessionLocal() as session:
        settings = await get_settings(message.chat.id)
        settings = await session.merge(settings)
        
        if text in ["0", "вимкнути"]:
            settings.quiet_hours_start = None
            settings.quiet_hours_end = None
            await session.commit()
            await message.answer("✅ Тихі години вимкнено.", reply_markup=get_main_menu_keyboard())
        else:
            try:
                parts = text.split("-")
                if len(parts) != 2: raise ValueError
                start_t = datetime.strptime(parts[0].strip(), "%H:%M").time()
                end_t = datetime.strptime(parts[1].strip(), "%H:%M").time()
                settings.quiet_hours_start = start_t
                settings.quiet_hours_end = end_t
                await session.commit()
                await message.answer(f"✅ Тихі години: {start_t.strftime('%H:%M')}-{end_t.strftime('%H:%M')}", reply_markup=get_main_menu_keyboard())
            except ValueError:
                return await message.answer("⚠️ Невірний формат. Введіть `ГГ:ХХ-ГГ:ХХ` або `0`.", parse_mode="Markdown")

    await state.clear()
    await cmd_settings(message, state) # Reshow settings

@router.callback_query(F.data == "set_reptime")
async def callback_set_reptime(callback: CallbackQuery, state: FSMContext):
    if not await verify_callback_admin_and_debounce(callback): return
    await state.set_state(SettingsTimeState.waiting_for_report_time)
    await callback.message.answer(
        "🕒 Введіть час відправки звітів у форматі `ГГ:ХХ` (наприклад `21:00`):",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(SettingsTimeState.waiting_for_report_time)
async def process_report_time(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        rep_t = datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return await message.answer("⚠️ Невірний формат. Введіть час у форматі `ГГ:ХХ` (наприклад `21:00`).", parse_mode="Markdown")

    async with AsyncSessionLocal() as session:
        settings = await get_settings(message.chat.id)
        settings = await session.merge(settings)
        settings.report_time = rep_t
        await session.commit()
    
    await message.answer(f"✅ Час звітів змінено на: {rep_t.strftime('%H:%M')}", reply_markup=get_main_menu_keyboard())
    await state.clear()
    await cmd_settings(message, state) # Reshow settings

@router.callback_query(F.data == "set_tz")
async def callback_set_tz(callback: CallbackQuery, state: FSMContext):
    if not await verify_callback_admin_and_debounce(callback): return
    await state.set_state(SettingsTimeState.waiting_for_timezone)
    await callback.message.answer(
        "🌍 Введіть назву часового поясу, наприклад `Europe/Kyiv`, `Europe/Warsaw`:",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(SettingsTimeState.waiting_for_timezone)
async def process_timezone(message: Message, state: FSMContext):
    import zoneinfo
    tz_name = message.text.strip()
    try:
        # validate timezone
        zoneinfo.ZoneInfo(tz_name)
    except Exception:
        return await message.answer("⚠️ Невідомий часовий пояс. Приклад: `Europe/Kyiv`.", parse_mode="Markdown")

    async with AsyncSessionLocal() as session:
        settings = await get_settings(message.chat.id)
        settings = await session.merge(settings)
        settings.timezone_name = tz_name
        await session.commit()
    
    await message.answer(f"✅ Часовий пояс змінено на: {tz_name}", reply_markup=get_main_menu_keyboard())
    await state.clear()
    await cmd_settings(message, state) # Reshow settings
