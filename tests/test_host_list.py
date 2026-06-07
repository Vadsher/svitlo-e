"""Unit tests for host list and management."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock, MagicMock
from aiogram.types import Message, User, Chat, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.handlers.host_list import cmd_list, callback_check, callback_toggle, callback_delete_confirm, EditAddressState, EditThresholdState, RenameState, callback_edit_address, callback_edit_threshold, callback_delete_execute, process_new_address, process_new_threshold, callback_rename, process_new_name
from src.database import Host

def create_mock_message(text: str = "/list") -> AsyncMock:
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
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_cmd_list_empty(mock_session_maker):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_msg = create_mock_message()
    await cmd_list(mock_msg)
    
    mock_msg.answer.assert_called_once()
    assert "📭 У цьому чаті немає доданих адрес." in mock_msg.answer.call_args[0][0]

@pytest.mark.asyncio
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_cmd_list_with_hosts(mock_session_maker):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost", status_up=True, is_active=True)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [host]
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_msg = create_mock_message()
    await cmd_list(mock_msg)
    
    mock_msg.answer.assert_called_once()
    text = mock_msg.answer.call_args[0][0]
    assert "MyHost" in text
    assert "1.1.1.1" in text

@pytest.mark.asyncio
@patch("src.handlers.host_list.verify_callback_admin_and_debounce", return_value=True)
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_callback_toggle(mock_session_maker, mock_verify):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost", is_active=True)
    mock_session.get.return_value = host
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_cb = create_mock_callback("toggle_1")
    await callback_toggle(mock_cb)
    
    assert host.is_active is False
    mock_cb.message.edit_reply_markup.assert_called_once()

@pytest.mark.asyncio
@patch("src.handlers.host_list.verify_callback_admin_and_debounce", return_value=True)
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_callback_delete_confirm(mock_session_maker, mock_verify):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost")
    mock_session.get.return_value = host
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_cb = create_mock_callback("delete_confirm_1")
    await callback_delete_confirm(mock_cb)
    
    # It shows confirmation first
    mock_cb.message.edit_text.assert_called_once()

@pytest.mark.asyncio
@patch("src.handlers.host_list.verify_callback_admin_and_debounce", return_value=True)
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_callback_edit_address_starts_fsm(mock_session_maker, mock_verify):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost")
    mock_session.get.return_value = host
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_cb = create_mock_callback("eadr_1")
    mock_state = create_mock_state()
    
    await callback_edit_address(mock_cb, state=mock_state)
    
    mock_state.update_data.assert_called_once_with(host_id=1)
    mock_state.set_state.assert_called_once_with(EditAddressState.waiting_for_address)

@pytest.mark.asyncio
@patch("src.handlers.host_list.verify_callback_admin_and_debounce", return_value=True)
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_callback_edit_threshold_starts_fsm(mock_session_maker, mock_verify):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost")
    mock_session.get.return_value = host
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_cb = create_mock_callback("ethresh_1")
    mock_state = create_mock_state()
    
    await callback_edit_threshold(mock_cb, state=mock_state)
    
    mock_state.update_data.assert_called_once_with(host_id=1)
    mock_state.set_state.assert_called_once_with(EditThresholdState.waiting_for_threshold)

@pytest.mark.asyncio
@patch("src.handlers.host_list.verify_callback_admin_and_debounce", return_value=True)
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_callback_delete_execute(mock_session_maker, mock_verify):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost")
    mock_session.get.return_value = host
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_cb = create_mock_callback("delete_execute_1")
    await callback_delete_execute(mock_cb)
    
    mock_session.delete.assert_called_once_with(host)
    mock_session.commit.assert_called_once()
    mock_cb.message.edit_text.assert_called_once()

@pytest.mark.asyncio
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_process_new_address_valid(mock_session_maker):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost")
    mock_session.get.return_value = host
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_msg = create_mock_message("8.8.8.8")
    mock_state = create_mock_state()
    mock_state.get_data.return_value = {"host_id": 1}
    
    await process_new_address(mock_msg, state=mock_state)
    
    assert host.address == "8.8.8.8"
    mock_session.commit.assert_called_once()
    mock_msg.answer.assert_called_once()
    mock_state.clear.assert_called_once()

@pytest.mark.asyncio
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_process_new_threshold_valid(mock_session_maker):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost")
    mock_session.get.return_value = host
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_msg = create_mock_message("5")
    mock_state = create_mock_state()
    mock_state.get_data.return_value = {"host_id": 1}
    
    await process_new_threshold(mock_msg, state=mock_state)
    
    assert host.ping_threshold == 5
    mock_session.commit.assert_called_once()
    mock_msg.answer.assert_called_once()
    mock_state.clear.assert_called_once()

@pytest.mark.asyncio
@patch("src.handlers.host_list.verify_callback_admin_and_debounce", return_value=True)
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_callback_rename_starts_fsm(mock_session_maker, mock_verify):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost")
    mock_session.get.return_value = host
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_cb = create_mock_callback("rename_1")
    mock_state = create_mock_state()
    
    await callback_rename(mock_cb, state=mock_state)
    
    mock_state.update_data.assert_called_once_with(host_id=1)
    mock_state.set_state.assert_called_once_with(RenameState.waiting_for_name)

@pytest.mark.asyncio
@patch("src.handlers.host_list.AsyncSessionLocal")
async def test_process_new_name_valid(mock_session_maker):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost")
    mock_session.get.return_value = host
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_msg = create_mock_message("NewHostName")
    mock_state = create_mock_state()
    mock_state.get_data.return_value = {"host_id": 1}
    
    await process_new_name(mock_msg, state=mock_state)
    
    assert host.pretty_name == "NewHostName"
    mock_session.commit.assert_called_once()
    mock_msg.answer.assert_called_once()
    mock_state.clear.assert_called_once()
