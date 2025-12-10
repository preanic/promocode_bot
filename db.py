import sqlite3
from datetime import datetime
import random
import string


def generate_promo_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


class Database:
    def __init__(self, path="promo_codes.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        query = """
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            promo_code TEXT UNIQUE NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            used_at TEXT
        );
        """
        self.conn.execute(query)
        self.conn.commit()

    def create_promo_code(self, user_id: int) -> str:
        while True:
            promo_code = generate_promo_code()
            query = "SELECT 1 FROM promo_codes WHERE promo_code = ?"
            cur = self.conn.execute(query, (promo_code,))
            if not cur.fetchone():
                insert_query = "INSERT INTO promo_codes(user_id, promo_code) VALUES (?, ?)"
                self.conn.execute(insert_query, (user_id, promo_code))
                self.conn.commit()
                return promo_code

    def check_promo_code(self, promo_code: str):
        query = "SELECT user_id, used FROM promo_codes WHERE promo_code = ?"
        cur = self.conn.execute(query, (promo_code,))
        return cur.fetchone()

    def mark_used(self, promo_code: str):
        query = "UPDATE promo_codes SET used = 1, used_at = ? WHERE promo_code = ?"
        self.conn.execute(query, (datetime.utcnow().isoformat(), promo_code))
        self.conn.commit()

    def has_promo_code(self, user_id: int) -> bool:
        cur = self.conn.execute("SELECT 1 FROM promo_codes WHERE user_id = ?", (user_id,))
        return cur.fetchone() is not None

    def count_promo_codes(self) -> tuple[int, int]:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM promo_codes WHERE used = 1")
        used_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM promo_codes WHERE used = 0")
        unused_count = cur.fetchone()[0]

        return used_count, unused_count


if __name__ == "__main__":
    db = Database()
    db.create_tables()
    print("Таблицы созданы")
