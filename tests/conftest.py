"""
Pytest global configuration and fixtures.
This file is loaded by pytest before any test modules are collected.
"""
import os

import tempfile

# Pre-flight Environment Mocking
# Set before imports to pass strict validation in src.config
os.environ["BOT_TOKEN"] = "mock_test_bot_token_12345"
os.environ["TZ"] = "Europe/Kyiv"

# Use a real temporary file instead of shared memory to avoid aiosqlite disk I/O and locking issues
temp_db = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
temp_db.close()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{temp_db.name}"

import pytest
import pytest_asyncio
from src.database import engine, Base, AsyncSessionLocal

@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Automatically create all tables before each test for a clean state."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
