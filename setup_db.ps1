# setup_db.ps1 — Run this after PostgreSQL 15 is installed
# Creates the voiceai user, database, and seeds initial data

$pgBin = "C:\Program Files\PostgreSQL\15\bin"
$env:PGPASSWORD = "postgres"   # postgres superuser password you set during install

Write-Host "=== Creating voiceai user and database ===" -ForegroundColor Cyan

# Create user
& "$pgBin\psql.exe" -U postgres -c "CREATE USER voiceai WITH PASSWORD 'voiceai_password';" 2>&1
& "$pgBin\psql.exe" -U postgres -c "CREATE DATABASE voiceai_db OWNER voiceai;" 2>&1
& "$pgBin\psql.exe" -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE voiceai_db TO voiceai;" 2>&1

Write-Host "=== Creating tables ===" -ForegroundColor Cyan

# Create tables via SQLAlchemy (run from backend directory)
Set-Location backend
& python -c "
import asyncio
from models.db_connection import async_engine
from models.database import Base

async def create():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created successfully')

asyncio.run(create())
"

Write-Host "=== Seeding initial data ===" -ForegroundColor Cyan

# Seed doctors and patients from init.sql
$env:PGPASSWORD = "voiceai_password"
& "$pgBin\psql.exe" -U voiceai -d voiceai_db -f "models\init.sql" 2>&1

Write-Host "=== Done! Database is ready. ===" -ForegroundColor Green
Set-Location ..