import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

async def list_users():
    load_dotenv()
    url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DATABASE_NAME", "fastapi_mvc_db")
    client = AsyncIOMotorClient(url)
    db = client[db_name]
    users = await db["users"].find().to_list(100)
    for u in users:
        print(f"User: {u['email']}, Role: {u['role']}, Active: {u['is_active']}")
    client.close()

if __name__ == "__main__":
    asyncio.run(list_users())
