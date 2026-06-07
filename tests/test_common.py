"""Unit tests for common handlers."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User, Chat
from aiogram.fsm.context import FSMContext

from src.handlers.common import cmd_start, cmd_help, cmd_about, cmd_cancel

def create_mock_message(text: str = "/start") -> AsyncMock:
    """Helper to create a fake aiogram Message object."""
    mock_msg = AsyncMock(spec=Message)
    mock_msg.text = text
    mock_msg.from_user = User(id=111222333, is_bot=False, first_name="TestUser")
    mock_msg.chat = Chat(id=111222333, type="private")
    mock_msg.answer = AsyncMock()
    return mock_msg

def create_mock_state(current_state=None) -> AsyncMock:
    """Helper to create a fake FSMContext object."""
    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_state = AsyncMock(return_value=current_state)
    mock_state.set_state = AsyncMock()
    mock_state.update_data = AsyncMock()
    mock_state.get_data = AsyncMock(return_value={})
    mock_state.clear = AsyncMock()
    return mock_state

@pytest.mark.asyncio
async def test_cmd_start():
    mock_msg = create_mock_message()
    mock_state = create_mock_state()
    await cmd_start(mock_msg, state=mock_state)
    mock_state.clear.assert_called_once()
    mock_msg.answer.assert_called_once()
    assert "Привіт" in mock_msg.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_cmd_help():
    mock_msg = create_mock_message("/help")
    await cmd_help(mock_msg)
    mock_msg.answer.assert_called_once()
    assert "💡 **Доступні команди:**" in mock_msg.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_cmd_about():
    mock_msg = create_mock_message("/about")
    await cmd_about(mock_msg)
    mock_msg.answer.assert_called_once()
    assert "🤖 **PingBot" in mock_msg.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_cmd_cancel():
    mock_msg = create_mock_message("❌ Скасувати")
    mock_state = create_mock_state()
    await cmd_cancel(mock_msg, state=mock_state)
    mock_state.clear.assert_called_once()
    mock_msg.answer.assert_called_once()
    assert "Немає активної операції." in mock_msg.answer.call_args[0][0]
