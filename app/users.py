"""Foydalanuvchilarni saqlash (upsert) bilan bog'liq yordamchi funksiyalar."""
from app import db
from app.config import CFG


async def upsert_user(tg_id: int, username=None, first_name=None, last_name=None) -> dict:
    await db.execute(
        """INSERT INTO users (tg_id, username, first_name, last_name)
           VALUES (%s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE
             username=VALUES(username),
             first_name=VALUES(first_name),
             last_name=VALUES(last_name),
             last_seen=CURRENT_TIMESTAMP""",
        (tg_id, username, first_name, last_name),
    )
    if tg_id in CFG.admin_ids:
        await db.execute("UPDATE users SET role='admin' WHERE tg_id=%s", (tg_id,))
    row = await db.fetch_one("SELECT * FROM users WHERE tg_id=%s", (tg_id,))
    return row or {
        "tg_id": tg_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "lang": "uz",
        "theme": "auto",
        "role": "admin" if tg_id in CFG.admin_ids else "user",
        "blocked": 0,
    }


def public_user(row: dict) -> dict:
    return {
        "id": row["tg_id"],
        "username": row.get("username"),
        "firstName": row.get("first_name"),
        "lastName": row.get("last_name"),
        "lang": row.get("lang") or "uz",
        "theme": row.get("theme") or "auto",
        "role": row.get("role") or "user",
        "createdAt": str(row.get("created_at") or ""),
    }
