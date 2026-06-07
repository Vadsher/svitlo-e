"""Unit tests for the report scheduler."""
import pytest
from datetime import datetime, time
import zoneinfo
from unittest.mock import AsyncMock, patch, MagicMock

from src.scheduler import generate_and_send_report, check_and_send_reports, setup_scheduler
from src.database import ChatSettings, Host

@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    return bot

@pytest.mark.asyncio
@patch("src.scheduler.AsyncSessionLocal")
async def test_generate_and_send_report_empty_skip(mock_session_maker, mock_bot):
    mock_session = AsyncMock()
    # No hosts or all hosts online
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    settings = ChatSettings(chat_id=111, report_skip_empty_daily=True)
    
    await generate_and_send_report(mock_bot, 111, "Щоденний", 24, skip_empty=True)
    
    # Bot shouldn't send anything if it's daily and we skip empty
    mock_bot.send_message.assert_not_called()

@pytest.mark.asyncio
@patch("src.scheduler.AsyncSessionLocal")
async def test_generate_and_send_report_no_skip(mock_session_maker, mock_bot):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost")
    mock_result = MagicMock()
    # First call is hosts, second is outages
    mock_result.scalars.return_value.all.side_effect = [[host], []]
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    settings = ChatSettings(chat_id=111, report_skip_empty_daily=False)
    
    await generate_and_send_report(mock_bot, 111, "Щоденний", 24, skip_empty=False)
    
    # Should send the "all online" message
    mock_bot.send_message.assert_called_once()
    assert "0 відключень" in mock_bot.send_message.call_args[0][1]

@pytest.mark.asyncio
@patch("src.scheduler.datetime")
@patch("src.scheduler.generate_and_send_report")
@patch("src.scheduler.AsyncSessionLocal")
async def test_check_and_send_reports(mock_session_maker, mock_generate, mock_datetime, mock_bot):
    mock_now = datetime(2026, 6, 8, 9, 0, 0, tzinfo=zoneinfo.ZoneInfo("Europe/Kyiv"))
    mock_datetime.now.return_value = mock_now
    
    mock_session = AsyncMock()
    # Create a setting for Kyiv timezone (UTC+3). 6:00 UTC = 9:00 Kyiv.
    # We set report_time to 09:00. It should trigger.
    settings = ChatSettings(
        chat_id=111, 
        report_enabled=True, 
        timezone_name="Europe/Kyiv", 
        report_time=time(9, 0),
        report_skip_empty_daily=False
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [settings]
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    await check_and_send_reports(mock_bot)
    
    mock_generate.assert_called_once_with(
        mock_bot,
        111,
        "Щоденний",
        24,
        skip_empty=False
    )

@pytest.mark.asyncio
@patch("src.scheduler.datetime")
@patch("src.scheduler.generate_and_send_report")
@patch("src.scheduler.AsyncSessionLocal")
async def test_check_and_send_reports_wrong_time(mock_session_maker, mock_generate, mock_datetime, mock_bot):
    mock_now_utc = datetime(2026, 6, 7, 6, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    mock_datetime.now.return_value = mock_now_utc
    
    mock_session = AsyncMock()
    # report_time is 10:00, but local time is 09:00
    settings = ChatSettings(
        chat_id=111, 
        report_enabled=True, 
        timezone_name="Europe/Kyiv", 
        report_time=time(10, 0)
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [settings]
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    await check_and_send_reports(mock_bot)
    
    mock_generate.assert_not_called()

@pytest.mark.asyncio
@patch("src.scheduler.datetime")
@patch("src.scheduler.generate_and_send_report")
@patch("src.scheduler.AsyncSessionLocal")
async def test_check_and_send_reports_disabled(mock_session_maker, mock_generate, mock_datetime, mock_bot):
    mock_now_utc = datetime(2026, 6, 7, 6, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    mock_datetime.now.return_value = mock_now_utc
    
    mock_session = AsyncMock()
    # report is disabled
    settings = ChatSettings(
        chat_id=111, 
        report_enabled=False, 
        timezone_name="Europe/Kyiv", 
        report_time=time(9, 0)
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [settings]
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    await check_and_send_reports(mock_bot)
    
    mock_generate.assert_not_called()

@pytest.mark.asyncio
@patch("src.scheduler.AsyncSessionLocal")
async def test_generate_and_send_report_send_error(mock_session_maker, mock_bot):
    mock_session = AsyncMock()
    host = Host(id=1, address="1.1.1.1", pretty_name="MyHost")
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.side_effect = [[host], []]
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_bot.send_message.side_effect = Exception("API error")
    
    await generate_and_send_report(mock_bot, 111, "Щоденний", 24, skip_empty=False)
    
    mock_bot.send_message.assert_called_once()
    # It should catch the exception and not crash

@pytest.mark.asyncio
@patch("src.scheduler.datetime")
@patch("src.scheduler.generate_and_send_report")
@patch("src.scheduler.AsyncSessionLocal")
async def test_check_and_send_reports_weekly_and_monthly(mock_session_maker, mock_generate, mock_datetime, mock_bot):
    # June 28, 2026 is a Sunday (weekly). June 30 is the last day of the month (monthly).
    # Let's use June 28, 2026 (Sunday) and fake calendar.monthrange to return 28.
    mock_now = datetime(2026, 6, 28, 9, 0, 0, tzinfo=zoneinfo.ZoneInfo("Europe/Kyiv"))
    mock_datetime.now.return_value = mock_now
    mock_datetime.strptime.return_value = datetime.strptime("09:00", "%H:%M")
    
    mock_session = AsyncMock()
    settings = ChatSettings(
        chat_id=111, 
        report_enabled=True, 
        timezone_name="Invalid/Timezone", # Will fallback to Europe/Kyiv
        report_time=time(9, 0),
        report_skip_empty_daily=False
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [settings]
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    with patch("src.scheduler.calendar.monthrange") as mock_monthrange:
        mock_monthrange.return_value = (0, 28) # Fake that month has 28 days
        await check_and_send_reports(mock_bot)
    
    assert mock_generate.call_count == 3
    # Called for daily, weekly, and monthly!

def test_setup_scheduler():
    bot = AsyncMock()
    scheduler = setup_scheduler(bot)
    assert scheduler is not None
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].name == "check_and_send_reports"
