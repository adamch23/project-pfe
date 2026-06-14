import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

async def check_user():
    load_dotenv()
    url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DATABASE_NAME", "fastapi_mvc_db")
    print(f"Connecting to {url}, database: {db_name}")
    client = AsyncIOMotorClient(url)
    db = client[db_name]
    user = await db["users"].find_one({"email": "adam2003y@gmail.com"})
    if user:
        print(f"User found: {user['email']}, active: {user['is_active']}, role: {user['role']}")
        if user.get("lockout_until") or user.get("failed_login_attempts"):
            print("Removing lockout/failed attempts...")
            await db["users"].update_one({"email": "adam2003y@gmail.com"}, {"$unset": {"lockout_until": "", "failed_login_attempts": ""}})
            print("Cleaned.")
    else:
        print("User NOT found")
    client.close()

if __name__ == "__main__":
    asyncio.run(check_user())
