#!/usr/bin/env python3
"""
Seed script — creates the initial super_admin user.

Usage:
  ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=yourpassword python seed_admin.py

Run this once after first deploy to create your account.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from truepresence.api.auth import hash_password
from truepresence.db import get_db, init_db

email = os.environ.get("ADMIN_EMAIL")
password = os.environ.get("ADMIN_PASSWORD")
name = os.environ.get("ADMIN_NAME", "Super Admin")

if not email or not password:
    print("ERROR: Set ADMIN_EMAIL and ADMIN_PASSWORD environment variables")
    sys.exit(1)

print("Initializing database schema...")
init_db()

with get_db() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (email.lower(),))
        existing = cur.fetchone()

        if existing:
            print(f"User {email} already exists — skipping")
        else:
            cur.execute(
                """INSERT INTO users (email, name, password, role, tenant_id)
                   VALUES (%s, %s, %s, 'super_admin', 'default')
                   RETURNING id, email, role""",
                (email.lower(), name, hash_password(password))
            )
            user = cur.fetchone()
            print(f"Created super_admin: {user['email']} (id={user['id']})")
