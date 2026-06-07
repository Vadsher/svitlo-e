"""Unit tests for settings management."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram.types import Message, User, Chat, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.handlers.settings import cmd_settings, callback_toggle_report, callback_toggle_skip_empty, callback_set_tz, callback_set_reptime, process_timezone, process_report_time, SettingsTimeState
from src.database import ChatSettings

def create_mock_message(text: str = "/settings") -> AsyncMock:
    mock_msg = AsyncMock(spec=Message)
    mock_msg.text = text
    mock_msg.from_user = User(id=111, is_bot=False, first_name="TestUser")
    mock_msg.chat = Chat(id=111, type="private")
    mock_msg.answer = AsyncMock()
    mock_msg.edit_text = AsyncMock()
    mock_msg.edit_reply_markup = AsyncMock()
    return mock_msg

def create_mock_callback(data: str) -> AsyncMock:
    mock_cb = AsyncMock(spec=CallbackQuery)
    mock_cb.data = data
    mock_cb.from_user = User(id=111, is_bot=False, first_name="TestUser")
    mock_cb.message = create_mock_message()
    mock_cb.answer = AsyncMock()
    return mock_cb

def create_mock_state() -> AsyncMock:
    mock_state = AsyncMock(spec=FSMContext)
    return mock_state

@pytest.mark.asyncio
@patch("src.handlers.settings.AsyncSessionLocal")
async def test_cmd_settings(mock_session_maker):
    mock_session = AsyncMock()
    settings = ChatSettings(chat_id=111)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = settings
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_msg = create_mock_message("/settings")
    mock_state = create_mock_state()
    await cmd_settings(mock_msg, state=mock_state)
    
    mock_msg.answer.assert_called_once()
    assert "Налаштування чату" in mock_msg.answer.call_args[0][0]

@pytest.mark.asyncio
@patch("src.handlers.settings.verify_callback_admin_and_debounce", return_value=True)
@patch("src.handlers.settings.AsyncSessionLocal")
async def test_callback_toggle_report(mock_session_maker, mock_verify):
    mock_session = AsyncMock()
    settings = ChatSettings(chat_id=111, quiet_hours_start=None, report_enabled=True)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = settings
    mock_session.execute.return_value = mock_result
    mock_session.merge.return_value = settings
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_cb = create_mock_callback("set_report_toggle")
    await callback_toggle_report(mock_cb)
    
    # Should toggle to False
    assert settings.report_enabled is False
    mock_session.commit.assert_called_once()
    mock_cb.message.edit_reply_markup.assert_called_once()

@pytest.mark.asyncio
@patch("src.handlers.settings.verify_callback_admin_and_debounce", return_value=True)
@patch("src.handlers.settings.AsyncSessionLocal")
async def test_callback_toggle_empty(mock_session_maker, mock_verify):
    mock_session = AsyncMock()
    settings = ChatSettings(chat_id=111, report_skip_empty_daily=False, quiet_hours_start=None)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = settings
    mock_session.execute.return_value = mock_result
    mock_session.merge.return_value = settings
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_cb = create_mock_callback("set_report_empty")
    await callback_toggle_skip_empty(mock_cb)
    
    # Should toggle to True
    assert settings.report_skip_empty_daily is True
    mock_session.commit.assert_called_once()

@pytest.mark.asyncio
@patch("src.handlers.settings.verify_callback_admin_and_debounce", return_value=True)
async def test_callback_set_tz_starts_fsm(mock_verify):
    mock_cb = create_mock_callback("set_tz")
    mock_state = create_mock_state()
    
    await callback_set_tz(mock_cb, state=mock_state)
    
    mock_state.set_state.assert_called_once_with(SettingsTimeState.waiting_for_timezone)
    mock_cb.message.answer.assert_called_once()

@pytest.mark.asyncio
@patch("src.handlers.settings.verify_callback_admin_and_debounce", return_value=True)
async def test_callback_set_reptime_starts_fsm(mock_verify):
    mock_cb = create_mock_callback("set_reptime")
    mock_state = create_mock_state()
    
    await callback_set_reptime(mock_cb, state=mock_state)
    
    mock_state.set_state.assert_called_once_with(SettingsTimeState.waiting_for_report_time)
    mock_cb.message.answer.assert_called_once()

@pytest.mark.asyncio
@patch("src.handlers.settings.AsyncSessionLocal")
async def test_process_timezone_valid(mock_session_maker):
    mock_session = AsyncMock()
    settings = ChatSettings(chat_id=111, quiet_hours_start=None)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = settings
    mock_session.execute.return_value = mock_result
    mock_session.merge.return_value = settings
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_msg = create_mock_message("Europe/Kyiv")
    mock_state = create_mock_state()
    
    await process_timezone(mock_msg, state=mock_state)
    
    assert settings.timezone_name == "Europe/Kyiv"
    mock_session.commit.assert_called_once()
    assert mock_msg.answer.call_count == 2
    assert mock_state.clear.call_count == 2

@pytest.mark.asyncio
@patch("src.handlers.settings.AsyncSessionLocal")
async def test_process_timezone_invalid(mock_session_maker):
    mock_msg = create_mock_message("Invalid/Timezone")
    mock_state = create_mock_state()
    
    await process_timezone(mock_msg, state=mock_state)
    
    # Should say invalid format and NOT clear state
    mock_msg.answer.assert_called_once()
    mock_state.clear.assert_not_called()

@pytest.mark.asyncio
@patch("src.handlers.settings.AsyncSessionLocal")
async def test_process_report_time_valid(mock_session_maker):
    mock_session = AsyncMock()
    settings = ChatSettings(chat_id=111, quiet_hours_start=None)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = settings
    mock_session.execute.return_value = mock_result
    mock_session.merge.return_value = settings
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_msg = create_mock_message("09:30")
    mock_state = create_mock_state()
    
    await process_report_time(mock_msg, state=mock_state)
    
    assert settings.report_time.hour == 9
    assert settings.report_time.minute == 30
    mock_session.commit.assert_called_once()
    assert mock_msg.answer.call_count == 2
    assert mock_state.clear.call_count == 2

@pytest.mark.asyncio
@patch("src.handlers.settings.AsyncSessionLocal")
async def test_process_report_time_invalid(mock_session_maker):
    mock_msg = create_mock_message("25:00")
    mock_state = create_mock_state()
    
    await process_report_time(mock_msg, state=mock_state)
    
    # Should say invalid format and NOT clear state
    mock_msg.answer.assert_called_once()
    mock_state.clear.assert_not_called()
