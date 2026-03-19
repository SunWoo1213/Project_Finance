import sys
import asyncio
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.app.db.session import AsyncSessionLocal
from backend.app.models import AIReport, Asset
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AIReport).join(Asset).where(Asset.ticker == 'BTC-USD').order_by(AIReport.created_at.desc()))
        report = res.scalars().first()
        if report:
            print(f"FOUND: {report.final_content[:100]}...")
            print(f"Bull Summary: {report.bull_summary[:100]}...")
        else:
            print("NOT FOUND")

asyncio.run(main())
