"""Test uchun: aiomysql interfeysini SQLite bilan taqlid qiluvchi soxta modul.

Faqat loyihada ishlatiladigan SQL gaplarni qo'llab-quvvatlaydi.
"""
import re
import sqlite3
import threading

_CONN = sqlite3.connect(":memory:", check_same_thread=False)
_CONN.row_factory = sqlite3.Row
_LOCK = threading.Lock()

# ON DUPLICATE KEY UPDATE uchun konflikt nishonlari
_CONFLICT = {
    "settings": "skey",
    "users": "tg_id",
    "orders": "order_code",
    "texts": "tkey, lang",
    "providers_cache": "provider_id",
    "products_cache": "product_id",
    "cache_meta": "mkey",
}


class DictCursor:
    pass


class Cursor:
    def __init__(self):
        self._cur = _CONN.cursor()
        self.lastrowid = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, sql, args=None):
        sql = translate(sql)
        with _LOCK:
            self._cur.execute(sql, args or ())
            _CONN.commit()
            self.lastrowid = self._cur.lastrowid

    async def fetchall(self):
        rows = self._cur.fetchall()
        return [dict(r) for r in rows]


class Connection:
    def cursor(self, cls=None):
        return Cursor()

    def close(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class Pool:
    def acquire(self):
        return _Acquire()

    def close(self):
        pass

    async def wait_closed(self):
        pass


class _Acquire:
    async def __aenter__(self):
        return Connection()

    async def __aexit__(self, *a):
        return False


async def connect(**kwargs):
    return Connection()


async def create_pool(**kwargs):
    return Pool()


# ---------------------------------------------------------------- SQL tarjima
def translate(sql: str) -> str:
    s = sql.strip()

    if s.upper().startswith("CREATE DATABASE"):
        return "SELECT 1"

    if s.upper().startswith("CREATE TABLE"):
        s = re.sub(r"\) ENGINE=[^;]*$", ")", s, flags=re.S)
        s = re.sub(r"\s+ON UPDATE CURRENT_TIMESTAMP", "", s)
        lines = []
        for line in s.splitlines():
            stripped = line.strip().rstrip(",")
            if re.match(r"^\s*KEY\s+\w+\s*\(", stripped):
                continue
            line = re.sub(r"UNIQUE KEY\s+\w+\s*", "UNIQUE ", line)
            line = re.sub(r"\b(BIG)?INT NOT NULL AUTO_INCREMENT PRIMARY KEY",
                          "INTEGER PRIMARY KEY AUTOINCREMENT", line, flags=re.I)
            lines.append(line)
        s = "\n".join(lines)
        s = re.sub(r",\s*\)", "\n)", s)  # KEY qatori o'chirilgandan keyingi ortiqcha vergul
        return s

    s = s.replace("INSERT IGNORE INTO", "INSERT OR IGNORE INTO")
    s = s.replace("NOW() - INTERVAL 1 DAY", "datetime('now', '-1 day')")
    s = s.replace("NOW()", "datetime('now')")

    m = re.search(r"INSERT INTO\s+(\w+)", s, re.I)
    table = m.group(1) if m else None

    s = re.sub(
        r"ON DUPLICATE KEY UPDATE\s+((?:\w+=(?:VALUES\(\w+\)|[A-Za-z_]+))(?:\s*,\s*\w+=(?:VALUES\(\w+\)|[A-Za-z_]+))*)",
        lambda mm: repl2(mm, table),
        s,
    )
    s = s.replace("%s", "?")
    return s


def repl2(match, table):
    part = match.group(1)
    pairs = re.findall(r"(\w+)=((?:VALUES\(\w+\))|[A-Za-z_]+)", part)
    tgt = _CONFLICT.get(table, "")
    sets = []
    for col, expr in pairs:
        if expr.upper().startswith("VALUES("):
            src = re.match(r"VALUES\((\w+)\)", expr, re.I).group(1)
            sets.append(f"{col}=excluded.{src}")
        else:
            sets.append(f"{col}={expr}")
    return f"ON CONFLICT({tgt}) DO UPDATE SET {', '.join(sets)}"
