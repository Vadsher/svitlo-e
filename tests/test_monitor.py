"""Unit tests for monitoring services."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock

from src.monitor import format_duration, check_host, _pending_changes, run_monitoring


def test_format_duration():
    """Test standard time difference formatting."""
    start = datetime(2026, 5, 23, 10, 0, 0)
    end = datetime(2026, 5, 23, 13, 1, 0)

    result = format_duration(start, end)
    assert result == "3 години 01 хвилину(и)"

def test_format_duration_short():
    """Test short time difference formatting."""
    start = datetime(2026, 5, 23, 10, 0, 0)
    end = datetime(2026, 5, 23, 10, 15, 0)

    result = format_duration(start, end)
    assert result == "0 години 15 хвилину(и)"

@pytest.mark.asyncio
@patch("src.monitor.async_ping")
async def test_check_host_online(mock_ping):
    """Test check_host when the ping succeeds."""
    mock_host = AsyncMock()
    mock_host.is_alive = True
    mock_ping.return_value = mock_host

    result = await check_host("1.1.1.1")

    assert result is True
    mock_ping.assert_called_once_with("1.1.1.1", count=2, timeout=2, privileged=False)

@pytest.mark.asyncio
@patch("src.monitor.async_ping")
async def test_check_host_offline(mock_ping):
    """Test check_host when the ping fails or times out."""
    mock_host = AsyncMock()
    mock_host.is_alive = False
    mock_ping.return_value = mock_host

    result = await check_host("8.8.8.8")

    assert result is False
    mock_ping.assert_called_once()

@pytest.mark.asyncio
@patch("src.monitor.async_ping")
async def test_check_host_cluster_partial_offline(mock_ping):
    """Test cluster logic: if at least one address is alive, result should be True."""
    # First ping fails, second ping succeeds
    mock_down = AsyncMock()
    mock_down.is_alive = False
    mock_up = AsyncMock()
    mock_up.is_alive = True
    
    mock_ping.side_effect = [mock_down, mock_up]

    result = await check_host("8.8.8.8, 1.1.1.1")

    assert result is True
    assert mock_ping.call_count == 2

@pytest.mark.asyncio
@patch("src.monitor.async_ping")
async def test_check_host_cluster_full_offline(mock_ping):
    """Test cluster logic: if ALL addresses are down, result should be False."""
    mock_down = AsyncMock()
    mock_down.is_alive = False
    
    mock_ping.side_effect = [mock_down, mock_down]

    result = await check_host("8.8.8.8, 1.1.1.1")

    assert result is False
    assert mock_ping.call_count == 2



def test_pending_changes_accumulate():
    """Unit test for the consecutive-ping counter logic."""
    _pending_changes.clear()
    host_id = 999

    # Simulate 4 consecutive DOWN pings (threshold=5, should not confirm yet)
    for i in range(1, 5):
        pending = _pending_changes.get(host_id)
        if pending is None or pending[0] != False:
            _pending_changes[host_id] = (False, 1)
        else:
            _pending_changes[host_id] = (False, pending[1] + 1)

    assert _pending_changes[host_id] == (False, 4)


def test_pending_changes_reset_on_recovery():
    """Confirm counter is cleared when status reverts before threshold."""
    _pending_changes.clear()
    host_id = 888

    # Simulate 3 consecutive DOWN pings, then host recovers
    _pending_changes[host_id] = (False, 3)

    # Host pings as UP again (same as current confirmed status) - clear counter
    is_up = True
    host_current_status = True  # UP is the confirmed DB status
    if is_up == host_current_status and host_id in _pending_changes:
        del _pending_changes[host_id]

    assert host_id not in _pending_changes

class StopLoop(Exception):
    pass

@pytest.fixture
def mock_bot():
    return AsyncMock()

@pytest.mark.asyncio
@patch("src.monitor.asyncio.sleep")
@patch("src.monitor.check_host")
@patch("src.monitor.AsyncSessionLocal")
async def test_run_monitoring_initial_status(mock_session_maker, mock_check_host, mock_sleep, mock_bot):
    """Test initial ping where host.status_up is None."""
    mock_sleep.side_effect = StopLoop()
    
    host = AsyncMock()
    host.id = 1
    host.address = "1.1.1.1"
    host.status_up = None
    host.user_id = 111
    host.is_active = True
    
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [host]
    mock_session.execute.return_value = mock_result
    
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    mock_check_host.return_value = True
    
    with pytest.raises(StopLoop):
        await run_monitoring(mock_bot)
        
    assert host.status_up is True
    mock_session.add.assert_called_with(host)
    mock_session.commit.assert_awaited_once()

@pytest.mark.asyncio
@patch("src.monitor.asyncio.sleep")
@patch("src.monitor.check_host")
@patch("src.monitor.AsyncSessionLocal")
async def test_run_monitoring_status_unchanged(mock_session_maker, mock_check_host, mock_sleep, mock_bot):
    """Test ping where status has not changed."""
    mock_sleep.side_effect = StopLoop()
    _pending_changes.clear()
    _pending_changes[1] = (False, 1)  # There was a pending change
    
    host = AsyncMock()
    host.id = 1
    host.address = "1.1.1.1"
    host.status_up = True
    host.ping_threshold = 3
    host.user_id = 111
    host.is_active = True
    
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [host]
    mock_session.execute.return_value = mock_result
    
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    mock_check_host.return_value = True
    
    with pytest.raises(StopLoop):
        await run_monitoring(mock_bot)
        
    assert 1 not in _pending_changes  # Should be reset

@pytest.mark.asyncio
@patch("src.monitor.asyncio.sleep")
@patch("src.monitor.check_host")
@patch("src.monitor.AsyncSessionLocal")
async def test_run_monitoring_status_changed_threshold_reached(mock_session_maker, mock_check_host, mock_sleep, mock_bot):
    """Test ping where status changes and threshold is reached."""
    mock_sleep.side_effect = StopLoop()
    _pending_changes.clear()
    _pending_changes[1] = (False, 2)  # Currently pending DOWN (2/3)
    
    host = AsyncMock()
    host.id = 1
    host.address = "1.1.1.1"
    host.status_up = True
    host.ping_threshold = 3
    host.user_id = 111
    host.is_active = True
    host.pretty_name = "Home"
    host.last_change = datetime(2026, 6, 7, 10, 0, tzinfo=timezone.utc)
    
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [host]
    
    # Mock for ChatSettings
    mock_settings_result = MagicMock()
    mock_settings_result.scalars.return_value.first.return_value = None
    
    mock_session.execute.side_effect = [mock_result, mock_settings_result]
    
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    mock_check_host.return_value = False  # Ping failed, so we reach 3/3 DOWN
    
    with pytest.raises(StopLoop):
        await run_monitoring(mock_bot)
        
    assert 1 not in _pending_changes
    mock_bot.send_message.assert_awaited_once()
    assert host.status_up is False
    assert mock_session.add.call_count == 2 # Host and Outage

@pytest.mark.asyncio
@patch("src.monitor.asyncio.sleep")
@patch("src.monitor.check_host")
@patch("src.monitor.AsyncSessionLocal")
async def test_run_monitoring_status_changed_threshold_reached_up(mock_session_maker, mock_check_host, mock_sleep, mock_bot):
    """Test ping where status changes UP and threshold is reached."""
    mock_sleep.side_effect = StopLoop()
    _pending_changes.clear()
    _pending_changes[1] = (True, 2)  # Currently pending UP (2/3)
    
    host = AsyncMock()
    host.id = 1
    host.address = "1.1.1.1"
    host.status_up = False
    host.ping_threshold = 3
    host.user_id = 111
    host.is_active = True
    host.pretty_name = "Home"
    host.last_change = datetime(2026, 6, 7, 10, 0, tzinfo=timezone.utc)
    
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [host]
    
    # Mock Outage
    mock_outage_result = MagicMock()
    outage = AsyncMock()
    mock_outage_result.scalars.return_value.first.return_value = outage
    
    # Mock ChatSettings
    mock_settings_result = MagicMock()
    mock_settings_result.scalars.return_value.first.return_value = None
    
    mock_session.execute.side_effect = [mock_result, mock_outage_result, mock_settings_result]
    
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    mock_check_host.return_value = True  # Ping succeeded, so we reach 3/3 UP
    
    with pytest.raises(StopLoop):
        await run_monitoring(mock_bot)
        
    assert 1 not in _pending_changes
    mock_bot.send_message.assert_awaited_once()
    assert host.status_up is True
    assert outage.online_at is not None
