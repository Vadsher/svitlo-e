"""Unit tests for host addition FSM workflow."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram.types import Message, User, Chat
from aiogram.fsm.context import FSMContext

from src.handlers.host_add import cmd_add, process_address, process_name, process_threshold, AddHostState
from src.database import Host

def create_mock_message(text: str = "/add") -> AsyncMock:
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
@patch("src.handlers.host_add.AsyncSessionLocal")
async def test_cmd_add_starts_fsm(mock_session_maker):
    """Test the /add command starts the FSM flow and sets waiting_for_address state."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    mock_msg = create_mock_message("/add")
    mock_state = create_mock_state()

    await cmd_add(mock_msg, state=mock_state)

    mock_state.set_state.assert_called_once_with(AddHostState.waiting_for_address)
    mock_msg.answer.assert_called_once()
    assert "Введіть IPv4-адресу" in mock_msg.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_process_address_invalid():
    """Test that invalid input re-prompts without advancing state."""
    mock_msg = create_mock_message("not-valid-addr!")
    mock_state = create_mock_state()

    await process_address(mock_msg, state=mock_state)

    mock_state.set_state.assert_not_called()
    mock_msg.answer.assert_called_once()
    assert "Невірний формат" in mock_msg.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_process_address_valid_ipv4():
    """Test that a valid IPv4 address advances the FSM to waiting_for_name."""
    mock_msg = create_mock_message("8.8.8.8")
    mock_state = create_mock_state()

    await process_address(mock_msg, state=mock_state)

    mock_state.update_data.assert_called_once_with(address="8.8.8.8")
    mock_state.set_state.assert_called_once_with(AddHostState.waiting_for_name)

@pytest.mark.asyncio
async def test_process_address_valid_cluster():
    """Test that a valid cluster format advances the FSM to waiting_for_name."""
    mock_msg = create_mock_message("8.8.8.8, example.com")
    mock_state = create_mock_state()

    await process_address(mock_msg, state=mock_state)

    mock_state.update_data.assert_called_once_with(address="8.8.8.8, example.com")
    mock_state.set_state.assert_called_once_with(AddHostState.waiting_for_name)

@pytest.mark.asyncio
async def test_process_name_advances_fsm():
    """Test that providing a name advances FSM to threshold."""
    mock_msg = create_mock_message("My Test Router")
    mock_state = create_mock_state()
    mock_state.get_data.return_value = {"address": "1.1.1.1"}
    
    await process_name(mock_msg, state=mock_state)
    
    mock_state.update_data.assert_called_once_with(pretty_name="My Test Router")
    mock_state.set_state.assert_called_once_with(AddHostState.waiting_for_threshold)

@pytest.mark.asyncio
@patch("src.handlers.host_add.AsyncSessionLocal")
async def test_process_threshold_valid(mock_session_maker):
    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_msg = create_mock_message("3")
    mock_state = create_mock_state()
    mock_state.get_data.return_value = {"address": "8.8.8.8", "pretty_name": "Google DNS"}
    
    await process_threshold(mock_msg, state=mock_state)
    
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    
    added_host = mock_session.add.call_args[0][0]
    assert isinstance(added_host, Host)
    assert added_host.ping_threshold == 3
    assert added_host.address == "8.8.8.8"
    assert added_host.pretty_name == "Google DNS"
    
    mock_state.clear.assert_called_once()
    assert "Додано:" in mock_msg.answer.call_args[0][0]

@pytest.mark.asyncio
@patch("src.handlers.host_add.AsyncSessionLocal")
async def test_process_threshold_skip(mock_session_maker):
    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_msg = create_mock_message("⏭️ Пропустити")
    mock_state = create_mock_state()
    mock_state.get_data.return_value = {"address": "1.1.1.1", "pretty_name": "Cloudflare"}
    
    await process_threshold(mock_msg, state=mock_state)
    
    added_host = mock_session.add.call_args[0][0]
    assert added_host.ping_threshold is None
    
@pytest.mark.asyncio
async def test_process_threshold_invalid():
    mock_msg = create_mock_message("not-a-number")
    mock_state = create_mock_state()
    mock_state.get_data.return_value = {"address": "1.1.1.1", "pretty_name": "Cloudflare"}
    
    await process_threshold(mock_msg, state=mock_state)
    
    mock_msg.answer.assert_called_once()
    assert "від 1 до 10" in mock_msg.answer.call_args[0][0]
    mock_state.clear.assert_not_called()
