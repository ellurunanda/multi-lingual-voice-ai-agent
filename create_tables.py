import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def create_tables():
    from models.db_connection import async_engine
    from models.database import Base
    print("Connecting to database...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully!")
    await async_engine.dispose()

asyncio.run(create_tables())