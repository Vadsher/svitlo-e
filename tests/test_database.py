"""Unit tests for database models and operations."""
import pytest
from sqlalchemy.future import select
from datetime import datetime, timezone

from src.database import AsyncSessionLocal, Host, Outage

@pytest.mark.asyncio
async def test_create_and_query_host():
    """Test creating a host and querying it from the database."""
    async with AsyncSessionLocal() as session:
        # Create a mock host
        new_host = Host(user_id=123456789, address="8.8.8.8", pretty_name="Google DNS")
        session.add(new_host)
        await session.commit()
        
        # Query the host back
        result = await session.execute(select(Host).where(Host.address == "8.8.8.8"))
        host = result.scalars().first()
        
        assert host is not None
        assert host.user_id == 123456789
        assert host.pretty_name == "Google DNS"
        assert host.is_active is True
        assert host.status_up is None

@pytest.mark.asyncio
async def test_outage_tracking():
    """Test creating an outage record linked to a host."""
    async with AsyncSessionLocal() as session:
        # 1. Setup a host
        host = Host(user_id=987654321, address="1.1.1.1", pretty_name="Cloudflare")
        session.add(host)
        await session.commit()
        
        # 2. Simulate internet going down
        offline_time = datetime.now(timezone.utc)
        outage = Outage(host_id=host.id, offline_at=offline_time)
        session.add(outage)
        await session.commit()
        
        # 3. Query outage
        result = await session.execute(select(Outage).where(Outage.host_id == host.id))
        saved_outage = result.scalars().first()
        
        assert saved_outage is not None
        assert saved_outage.host_id == host.id
        assert saved_outage.online_at is None
        
        # 4. Simulate internet coming back
        online_time = datetime.now(timezone.utc)
        saved_outage.online_at = online_time
        await session.commit()
        
        assert saved_outage.online_at == online_time
