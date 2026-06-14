import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json

async def view_audit_trail():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["fastapi_mvc_db"]
    logs = await db["audit_logs"].find().sort("timestamp", -1).limit(5).to_list(None)
    
    print("\n📜 DERNIÈRES ACTIONS D'AUDIT (Top 5) :\n")
    for log in logs:
        print(f"[{log.get('timestamp')}] {log.get('action')} sur {log.get('entity')} par {log.get('username') or 'Système'}")
        print(f"   Status: {log.get('status')} | IP: {log.get('ip_address')}")
        print(f"   Signature: {log.get('signature')[:20]}...")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(view_audit_trail())
