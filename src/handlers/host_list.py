import logging
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.future import select

from src.database import AsyncSessionLocal, Host
from src.config import STATUS_CHANGE_THRESHOLD
from src.monitor import check_host
from src.filters import IsAdminFilter
from src.handlers.utils import (
    check_is_admin, get_main_menu_keyboard, get_cancel_keyboard,
    verify_callback_admin_and_debounce, is_valid_address
)

logger = logging.getLogger(__name__)
router = Router()

class RenameState(StatesGroup):
    waiting_for_name = State()
    host_id = State()

class EditAddressState(StatesGroup):
    waiting_for_address = State()
    host_id = State()

class EditThresholdState(StatesGroup):
    waiting_for_threshold = State()
    host_id = State()

def get_host_keyboard(host_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Generate inline keyboard for host management."""
    buttons = [
        [InlineKeyboardButton(text="🔍 Перевірити", callback_data=f"check_{host_id}")],
        [
            InlineKeyboardButton(text="⏸ Пауза" if is_active else "▶️ Продовжити", callback_data=f"toggle_{host_id}"),
            InlineKeyboardButton(text="⚙️ Чутливість", callback_data=f"ethresh_{host_id}")
        ],
        [
            InlineKeyboardButton(text="✏️ Назва", callback_data=f"rename_{host_id}"),
            InlineKeyboardButton(text="✏️ Адреса/Кластер", callback_data=f"eadr_{host_id}")
        ],
        [InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"delete_confirm_{host_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_delete_confirm_keyboard(host_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Так, видалити", callback_data=f"delete_execute_{host_id}"),
            InlineKeyboardButton(text="↩️ Назад", callback_data=f"delete_cancel_{host_id}"),
        ]
    ])

@router.message(Command("list"))
async def cmd_list(message: Message):
    await _show_list(message)

@router.message(F.text == "📋 Мій список")
async def btn_list(message: Message):
    await _show_list(message)

async def _show_list(message: Message) -> None:
    is_admin = await check_is_admin(message)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Host).where(Host.user_id == message.chat.id))
        hosts = result.scalars().all()

        if not hosts:
            await message.answer(
                "📭 У цьому чаті немає доданих адрес.",
                reply_markup=get_main_menu_keyboard() if is_admin else None,
            )
            return

        for h in hosts:
            status = "🟢 Світло є" if h.status_up else "🔴 Світло вимкнено"
            paused = " (ПАУЗА)" if not h.is_active else ""
            thresh = f" (Чутливість: {h.ping_threshold})" if h.ping_threshold else ""
            text = f"🖥 *{h.pretty_name}* (`{h.address}`){thresh}\nСтатус: {status}{paused}"
            
            await message.answer(
                text, 
                parse_mode="Markdown", 
                reply_markup=get_host_keyboard(h.id, h.is_active) if is_admin else None
            )

# ── Inline Callbacks ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("check_"))
async def callback_check(callback: CallbackQuery):
    if not await verify_callback_admin_and_debounce(callback): return
        
    host_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host:
            return await callback.answer("Хост не знайдено", show_alert=True)

        await callback.answer(f"Перевіряю {host.pretty_name}...", show_alert=False)
        addresses = [p.strip() for p in host.address.split(',')]
        tasks = [check_host(addr) for addr in addresses]
        results = await asyncio.gather(*tasks)
        is_up = any(results)
        
        status = "🟢 Світло є" if is_up else "🔴 Світло вимкнено"
        await callback.message.reply(f"Поточний статус *{host.pretty_name}*: {status}", parse_mode="Markdown")

@router.callback_query(F.data.startswith("toggle_"))
async def callback_toggle(callback: CallbackQuery):
    if not await verify_callback_admin_and_debounce(callback): return
        
    host_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if host:
            host.is_active = not host.is_active
            await session.commit()
            action = "відновлено" if host.is_active else "призупинено"
            await callback.message.edit_reply_markup(reply_markup=get_host_keyboard(host.id, host.is_active))
            await callback.answer(f"Моніторинг {host.pretty_name} {action}")

@router.callback_query(F.data.startswith("rename_"))
async def callback_rename(callback: CallbackQuery, state: FSMContext):
    if not await verify_callback_admin_and_debounce(callback): return
        
    host_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host: return await callback.answer("Хост не знайдено", show_alert=True)
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
    data = await state.get_data()
    host_id = data.get("host_id")

    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if host:
            old_name = host.pretty_name
            host.pretty_name = message.text[:50]
            await session.commit()
            await message.answer(
                f"✅ Назву змінено: *{old_name}* → *{host.pretty_name}*",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
            )
    await state.clear()


@router.callback_query(F.data.startswith("eadr_"))
async def callback_edit_address(callback: CallbackQuery, state: FSMContext):
    if not await verify_callback_admin_and_debounce(callback): return
        
    host_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host: return await callback.answer("Хост не знайдено", show_alert=True)
        current_addr = host.address
        host_name = host.pretty_name

    await state.update_data(host_id=host_id)
    await state.set_state(EditAddressState.waiting_for_address)
    await callback.message.answer(
        f"✏️ Редагування **{host_name}**\nПоточна адреса/кластер: `{current_addr}`\nВведіть нові IPv4 або домени (через кому):", 
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(EditAddressState.waiting_for_address)
async def process_new_address(message: Message, state: FSMContext):
    address = message.text.strip()
    addresses = [a.strip() for a in address.split(',')]
    valid = all(is_valid_address(a) for a in addresses if a)
    
    if not valid or not addresses:
        await message.answer(
            "⚠️ Невірний формат.\nВведіть коректні *IPv4-адреси* або *доменні імена* через кому.",
            parse_mode="Markdown"
        )
        return

    data = await state.get_data()
    host_id = data.get("host_id")

    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if host:
            host.address = address
            await session.commit()
            await message.answer(
                f"✅ Адреси оновлено на: `{address}`",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
            )
    await state.clear()


@router.callback_query(F.data.startswith("ethresh_"))
async def callback_edit_threshold(callback: CallbackQuery, state: FSMContext):
    if not await verify_callback_admin_and_debounce(callback): return
        
    host_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host: return await callback.answer("Хост не знайдено", show_alert=True)
        current_thresh = host.ping_threshold or f"За замовчуванням ({STATUS_CHANGE_THRESHOLD})"
        host_name = host.pretty_name

    await state.update_data(host_id=host_id)
    await state.set_state(EditThresholdState.waiting_for_threshold)
    await callback.message.answer(
        f"⚙️ Чутливість для **{host_name}**\nПоточна чутливість: `{current_thresh}`\nВведіть нове значення від 1 до 10 (або 0 для скидання):", 
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(EditThresholdState.waiting_for_threshold)
async def process_new_threshold(message: Message, state: FSMContext):
    try:
        val = int(message.text.strip())
        if not (0 <= val <= 10):
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть коректне ціле число від 0 до 10.")
        return

    data = await state.get_data()
    host_id = data.get("host_id")

    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if host:
            host.ping_threshold = val if val > 0 else None
            await session.commit()
            msg = f"✅ Чутливість оновлено: `{val}`" if val > 0 else "✅ Чутливість скинуто до стандартної."
            await message.answer(
                msg,
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
            )
    await state.clear()

# ── Delete Host ───────────────────────────────────────────────────────────────

async def _show_delete_list(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Host).where(Host.user_id == message.chat.id))
        hosts = result.scalars().all()

        if not hosts:
            await message.answer("📭 У вас немає доданих адрес.", reply_markup=get_main_menu_keyboard())
            return

        await message.answer("🗑️ Оберіть адресу для видалення, натиснувши *Видалити* під потрібним хостом:", parse_mode="Markdown")
        for h in hosts:
            status = "🟢 Світло є" if h.status_up else "🔴 Світло вимкнено"
            text = f"🖥 *{h.pretty_name}* (`{h.address}`)\nСтатус: {status}"
            await message.answer(text, parse_mode="Markdown", reply_markup=get_host_keyboard(h.id, h.is_active))

@router.message(Command("delete"), IsAdminFilter())
async def cmd_delete(message: Message):
    await _show_delete_list(message)

@router.message(F.text == "🗑️ Видалити адресу", IsAdminFilter())
async def btn_delete(message: Message):
    await _show_delete_list(message)

@router.callback_query(F.data.startswith("delete_confirm_"))
async def callback_delete_confirm(callback: CallbackQuery):
    if not await verify_callback_admin_and_debounce(callback): return
        
    host_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host: return await callback.answer("Хост не знайдено", show_alert=True)

    await callback.message.edit_text(
        f"❓ Ви дійсно хочете видалити хост *{host.pretty_name}* (`{host.address}`)?\nЦю дію неможливо скасувати.",
        parse_mode="Markdown",
        reply_markup=get_delete_confirm_keyboard(host_id),
    )
    await callback.answer()

@router.callback_query(F.data.startswith("delete_execute_"))
async def callback_delete_execute(callback: CallbackQuery):
    if not await verify_callback_admin_and_debounce(callback): return
        
    host_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host: return await callback.answer("Хост не знайдено", show_alert=True)

        name, address = host.pretty_name, host.address
        await session.delete(host)
        await session.commit()

    await callback.message.edit_text(f"🗑️ *{name}* (`{address}`) видалено.", parse_mode="Markdown")
    await callback.answer("Видалено")

@router.callback_query(F.data.startswith("delete_cancel_"))
async def callback_delete_cancel(callback: CallbackQuery):
    if not await verify_callback_admin_and_debounce(callback): return
        
    host_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        host = await session.get(Host, host_id)
        if not host: return await callback.answer()

    await callback.message.edit_reply_markup(reply_markup=get_host_keyboard(host_id, host.is_active))
    await callback.answer("Скасовано")
