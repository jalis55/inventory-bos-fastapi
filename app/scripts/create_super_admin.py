# app/scripts/create_super_admin.py
#!/usr/bin/env python
"""
Super Admin Creation Script
Run: python -m app.scripts.create_super_admin
"""

from sqlalchemy import select
from app.utils.security import hash_password
from app.models.user import User, Role
from app.db.database import AsyncSessionLocal
import sys
import asyncio
import getpass
from pathlib import Path
from art import tprint

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent.parent))


async def main():
    async with AsyncSessionLocal() as db:
        try:
            # Print centered header
            tprint("Super Admin")
            print()

            # Check if super admin already exists
            # stmt = select(User).where(User.role == Role.SUPER_ADMIN)
            # result = await db.execute(stmt)
            # existing = result.scalar_one_or_none()

            # if existing:
            #     print(f"⚠️  Super admin already exists!")
            #     print(f"   Email: {existing.email}")
            #     print(f"   Full Name: {existing.full_name}")

            #     choice = input("\nCreate another super admin? (y/N): ")
            #     if choice.lower() != 'y':
            #         print("❌ Exiting...")
            #         return

            # Get inputs
            print("\n Enter admin details:\n")

            email = input("Email: ").strip()
            if not email:
                print("❌ Email is required")
                return

            full_name = input("Full Name: ").strip()
            if not full_name:
                print("❌ Full Name is required")
                return

            # Check if email already exists
            stmt = select(User).where(User.email == email)
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                print(f"❌ Email '{email}' already registered")
                return

            # Get password
            password = getpass.getpass("Password: ")
            confirm_password = getpass.getpass("Confirm Password: ")

            if password != confirm_password:
                print("❌ Passwords do not match")
                return

            if len(password) < 8:
                print("❌ Password must be at least 8 characters")
                return

            # Confirm before saving
            print("\n" + "="*60)
            print(f"{'Summary':-^60}")
            print(f"   Email: {email}")
            print(f"   Full Name: {full_name}")
            print(f"   Role: {Role.SUPER_ADMIN.value}")
            print("="*60)

            confirm = input("\nCreate super admin? (y/N): ")
            if confirm.lower() != 'y':
                print("❌ Creation cancelled")
                return

            # Create super admin
            admin = User(
                email=email,
                full_name=full_name,
                hashed_password=hash_password(password),
                role=Role.SUPER_ADMIN,
                is_active=True
            )
            print(admin)

            db.add(admin)
            await db.commit()
            await db.refresh(admin)

            # Print success message
            print()
            print(f"{'Successful':-^60}")
            print(f"   ID: {admin.id}")
            print(f"   Email: {admin.email}")
            print(f"   Full Name: {admin.full_name}")
            print(f"   Role: {admin.role}")
            print(f"   Active: {admin.is_active}")
            print("="*60)
            print("\n⚠️  Please keep your password safe!")

        except KeyboardInterrupt:
            print("\n\n❌ Operation cancelled by user")
        except Exception as e:
            await db.rollback()
            print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
