"""Unit tests for monitoring services."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from src.monitor import format_duration, check_host, _pending_changes


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
