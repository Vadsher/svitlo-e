"""Background monitoring service."""
import asyncio
import logging
from datetime import datetime, timezone

from icmplib import async_ping
from sqlalchemy.future import select

from src.database import AsyncSessionLocal, Host, Outage
from src.config import KYIV_TZ, STATUS_CHANGE_THRESHOLD

logger = logging.getLogger(__name__)

# Tracks unconfirmed (pending) status changes per host.
# Format: {host_id: (pending_status: bool, consecutive_count: int)}
# - pending_status: the new status being accumulated (True=UP, False=DOWN)
# - consecutive_count: how many pings in a row have returned pending_status
_pending_changes: dict[int, tuple[bool, int]] = {}


def format_duration(start: datetime, end: datetime) -> str:
    """Calculate and format the time duration between two dates."""
    diff = end - start
    hours, remainder = divmod(diff.total_seconds(), 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{int(hours)} години {int(minutes):02d} хвилину(и)"

def format_time(dt: datetime) -> str:
    """Format datetime object to Kyiv timezone string."""
    return dt.astimezone(KYIV_TZ).strftime("%H:%M")

async def check_host(address: str) -> bool:
    """Execute ICMP ping to the specified address."""
    try:
        host = await async_ping(address, count=2, timeout=2, privileged=False)
        return host.is_alive
    except Exception as e:
        logger.error(f"Ping error for {address}: {e}")
        return False


async def run_monitoring(bot) -> None:
    """Main loop for parallel background host monitoring.

    Status change logic (consecutive-ping threshold):
      - Each minute, all active hosts are pinged in parallel.
      - If a ping result differs from the current confirmed DB status, a counter
        in _pending_changes is incremented.
      - If the same new result appears STATUS_CHANGE_THRESHOLD times IN A ROW,
        the status is confirmed: the DB is updated and a Telegram notification is sent.
      - If the host recovers before the threshold is reached, the counter is reset
        silently - no notification is ever sent.
    """
    logger.info(
        f"Starting background monitoring "
        f"(threshold: {STATUS_CHANGE_THRESHOLD} consecutive pings to confirm change)."
    )
    while True:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Host).where(Host.is_active == True))
                hosts = result.scalars().all()

                if hosts:
                    tasks = [check_host(h.address) for h in hosts]
                    results = await asyncio.gather(*tasks)
                    now = datetime.now(timezone.utc)

                    for host, is_up in zip(hosts, results):

                        # ── First-ever ping ──────────────────────────────────
                        if host.status_up is None:
                            host.status_up = is_up
                            host.last_change = now
                            session.add(host)
                            logger.info(
                                f"Host {host.address} initial status: "
                                f"{'UP' if is_up else 'DOWN'}"
                            )
                            continue

                        # ── Status unchanged from confirmed value ────────────
                        if is_up == host.status_up:
                            # If there was a pending counter for this host, the
                            # host recovered before the threshold - reset silently.
                            if host.id in _pending_changes:
                                logger.info(
                                    f"Host {host.address}: status reverted before "
                                    f"threshold ({_pending_changes[host.id][1]}"
                                    f"/{STATUS_CHANGE_THRESHOLD}). Counter reset."
                                )
                                del _pending_changes[host.id]
                            continue

                        # ── Status differs from confirmed value ──────────────
                        pending = _pending_changes.get(host.id)

                        if pending is None or pending[0] != is_up:
                            # First detection of this change direction (or direction flipped).
                            _pending_changes[host.id] = (is_up, 1)
                            logger.info(
                                f"Host {host.address}: possible status change "
                                f"to {'UP' if is_up else 'DOWN'} detected. "
                                f"1/{STATUS_CHANGE_THRESHOLD}"
                            )
                        else:
                            # Another consecutive ping confirms the same new status.
                            new_count = pending[1] + 1

                            if new_count >= STATUS_CHANGE_THRESHOLD:
                                # ── Threshold reached → confirm change ───────
                                del _pending_changes[host.id]
                                prev_time = host.last_change or now
                                duration_str = format_duration(prev_time, now)
                                time_range = f"🕒 {format_time(prev_time)} по {format_time(now)}"

                                if is_up:
                                    msg = (
                                        f"💡 *Світло з'явилось* ({host.pretty_name})\n"
                                        f"Світла не було {duration_str} {time_range}"
                                    )
                                    logger.info(f"Host {host.address} confirmed UP.")
                                    outage_res = await session.execute(
                                        select(Outage).where(
                                            Outage.host_id == host.id,
                                            Outage.online_at == None,
                                        )
                                    )
                                    outage = outage_res.scalars().first()
                                    if outage:
                                        outage.online_at = now
                                else:
                                    msg = (
                                        f"🌑 *Світло зникло* ({host.pretty_name})\n"
                                        f"Світло було {duration_str} {time_range}"
                                    )
                                    logger.info(f"Host {host.address} confirmed DOWN.")
                                    session.add(Outage(host_id=host.id, offline_at=now))

                                await bot.send_message(
                                    host.user_id, msg, parse_mode="Markdown"
                                )
                                host.status_up = is_up
                                host.last_change = now
                                session.add(host)

                            else:
                                # Still accumulating - not yet confirmed.
                                _pending_changes[host.id] = (is_up, new_count)
                                logger.info(
                                    f"Host {host.address}: consecutive "
                                    f"{'UP' if is_up else 'DOWN'} "
                                    f"{new_count}/{STATUS_CHANGE_THRESHOLD}"
                                )

                    await session.commit()

        except Exception as e:
            logger.error(f"Monitoring loop error: {e}", exc_info=True)

        await asyncio.sleep(60)
