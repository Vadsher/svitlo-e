import logging
from datetime import datetime, timedelta, timezone
import zoneinfo
import calendar
from sqlalchemy import select, and_
from aiogram import Bot

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.database import AsyncSessionLocal, Host, Outage, ChatSettings

logger = logging.getLogger(__name__)

async def generate_and_send_report(bot: Bot, chat_id: int, period_name: str, hours_back: int, skip_empty: bool = False):
    """Generate and send outage report for a given time period for a specific chat."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours_back)
    
    async with AsyncSessionLocal() as session:
        hosts_result = await session.execute(select(Host).where(Host.user_id == chat_id))
        hosts = hosts_result.scalars().all()
        if not hosts:
            return
            
        report_lines = []
        total_outages_overall = 0
        
        for h in hosts:
            outages_result = await session.execute(
                select(Outage).where(
                    and_(
                        Outage.host_id == h.id,
                        Outage.offline_at >= start_time
                    )
                )
            )
            outages = outages_result.scalars().all()
            
            total_outages = len(outages)
            total_outages_overall += total_outages
            if total_outages > 0:
                total_duration = timedelta()
                for o in outages:
                    end_t = o.online_at if o.online_at else now
                    total_duration += (end_t - o.offline_at)
                
                total_hours = int(total_duration.total_seconds() // 3600)
                total_minutes = int((total_duration.total_seconds() % 3600) // 60)
                
                report_lines.append(f"🖥 *{h.pretty_name}*: {total_outages} відключень (загалом {total_hours}г {total_minutes}хв)")
            else:
                report_lines.append(f"🖥 *{h.pretty_name}*: 0 відключень (100% онлайн)")
        
        if skip_empty and total_outages_overall == 0:
            logger.info(f"Skipping empty report for {chat_id}")
            return
            
        if report_lines:
            msg = f"📊 **{period_name.capitalize()} звіт про відключення:**\n\n" + "\n".join(report_lines)
            try:
                await bot.send_message(chat_id, msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send report to {chat_id}: {e}")

async def check_and_send_reports(bot: Bot):
    """Run every minute, check which chats need reports right now based on their settings."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ChatSettings).where(ChatSettings.report_enabled == True))
        settings = result.scalars().all()
        
    for s in settings:
        try:
            tz = zoneinfo.ZoneInfo(s.timezone_name or "Europe/Kyiv")
        except Exception:
            tz = zoneinfo.ZoneInfo("Europe/Kyiv")
            
        local_now = datetime.now(tz)
        rep_time = s.report_time or datetime.strptime("21:00", "%H:%M").time()
        
        if local_now.hour == rep_time.hour and local_now.minute == rep_time.minute:
            logger.info(f"Triggering reports for chat {s.chat_id} at {local_now.strftime('%H:%M')}")
            
            # Send daily
            await generate_and_send_report(bot, s.chat_id, "Щоденний", 24, skip_empty=s.report_skip_empty_daily)
            
            # Send weekly (if Sunday)
            if local_now.weekday() == 6:
                await generate_and_send_report(bot, s.chat_id, "Щотижневий", 24 * 7, skip_empty=False)
                
            # Send monthly (if last day of the month)
            last_day = calendar.monthrange(local_now.year, local_now.month)[1]
            if local_now.day == last_day:
                await generate_and_send_report(bot, s.chat_id, "Щомісячний", 24 * 30, skip_empty=False)

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Initialize and configure the scheduler."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_send_reports, "cron", minute="*", args=[bot])
    return scheduler
