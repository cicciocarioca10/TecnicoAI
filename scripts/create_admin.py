"""
Create an admin user.

Usage:
    python scripts/create_admin.py --email admin@tecnicoai.it --password admin1234 --name "Admin"
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from db.database import AsyncSessionLocal, init_db, get_user_by_email, create_user
from services.auth_service import hash_password


async def main() -> None:
    parser = argparse.ArgumentParser(description="Create TecnicoAI admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    if len(args.password) < 8:
        print("Error: password must be at least 8 characters")
        sys.exit(1)

    await init_db()

    async with AsyncSessionLocal() as db:
        existing = await get_user_by_email(db, args.email)
        if existing:
            print(f"User already exists: {args.email} (id={existing.id})")
            sys.exit(0)
        user = await create_user(
            db,
            email=args.email,
            password_hash=hash_password(args.password),
            full_name=args.name,
            is_admin=True,
        )
        print(f"Admin created: {user.email} (id={user.id})")


asyncio.run(main())
