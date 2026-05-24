"""Unit tests for Telegram bot handlers."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User, Chat
from aiogram.fsm.context import FSMContext

from src.handlers import cmd_start, cmd_add, process_address
from src.handlers import AddHostState
from src.database import AsyncSessionLocal, Host
from sqlalchemy.future import select


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
    """Test the /start command replies with welcome message and clears state."""
    mock_msg = create_mock_message()
    mock_state = create_mock_state()

    await cmd_start(mock_msg, state=mock_state)

    mock_state.clear.assert_called_once()
    mock_msg.answer.assert_called_once()
    args, kwargs = mock_msg.answer.call_args
    assert "Привіт" in args[0]


@pytest.mark.asyncio
async def test_cmd_add_starts_fsm():
    """Test the /add command starts the FSM flow and sets waiting_for_address state."""
    mock_msg = create_mock_message("/add")
    mock_state = create_mock_state()

    await cmd_add(mock_msg, state=mock_state)

    mock_state.set_state.assert_called_once_with(AddHostState.waiting_for_address)
    mock_msg.answer.assert_called_once()


@pytest.mark.asyncio
async def test_process_address_invalid():
    """Test that invalid input re-prompts without advancing state."""
    mock_msg = create_mock_message("not-valid-addr!")
    mock_state = create_mock_state()

    await process_address(mock_msg, state=mock_state)

    # State must NOT advance
    mock_state.set_state.assert_not_called()
    mock_state.update_data.assert_not_called()
    mock_msg.answer.assert_called_once()
    args, _ = mock_msg.answer.call_args
    assert "Невірний формат" in args[0]


@pytest.mark.asyncio
async def test_process_address_valid_ipv4():
    """Test that a valid IPv4 address advances the FSM to waiting_for_name."""
    mock_msg = create_mock_message("8.8.8.8")
    mock_state = create_mock_state()

    await process_address(mock_msg, state=mock_state)

    mock_state.update_data.assert_called_once_with(address="8.8.8.8")
    mock_state.set_state.assert_called_once_with(AddHostState.waiting_for_name)


@pytest.mark.asyncio
async def test_process_address_valid_domain():
    """Test that a valid domain name advances the FSM to waiting_for_name."""
    mock_msg = create_mock_message("example.com")
    mock_state = create_mock_state()

    await process_address(mock_msg, state=mock_state)

    mock_state.update_data.assert_called_once_with(address="example.com")
    mock_state.set_state.assert_called_once_with(AddHostState.waiting_for_name)
