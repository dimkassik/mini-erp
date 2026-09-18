"""Работа с базой данных SQLite: схема, подключение, тестовые данные."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "erp.db"

# Схема БД. Этот же текст отдаётся LLM, чтобы она знала, какие есть таблицы.
SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT,
    city       TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    category   TEXT,
    price      REAL NOT NULL,      -- цена за единицу, в тенге
    stock      INTEGER NOT NULL DEFAULT 0  -- остаток на складе
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    INTEGER NOT NULL,
    total       REAL NOT NULL,     -- quantity * price на момент заказа
    status      TEXT NOT NULL DEFAULT 'new',  -- new / paid / shipped
    created_at  TEXT NOT NULL DEFAULT (date('now'))  -- формат YYYY-MM-DD
);
"""


def get_conn(readonly: bool = False) -> sqlite3.Connection:
    """Открыть подключение. readonly=True — только чтение (для SQL от LLM)."""
    if readonly:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # строки как словари: row["name"]
    return conn


def init_db() -> None:
    """Создать таблицы и залить тестовые данные, если база пустая."""
    conn = get_conn()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        seed(conn)
    conn.commit()
    conn.close()


def seed(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO customers (name, email, city) VALUES (?, ?, ?)",
        [
            ("ТОО Альфа", "alfa@mail.kz", "Алматы"),
            ("ИП Бекова", "bekova@mail.kz", "Астана"),
            ("ТОО Каспий", "kaspiy@mail.kz", "Актау"),
            ("ИП Серик", "serik@mail.kz", "Алматы"),
        ],
    )
    conn.executemany(
        "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
        [
            ("Ноутбук Lenovo", "Техника", 350000, 12),
            ("Монитор Samsung 27", "Техника", 120000, 3),
            ("Офисное кресло", "Мебель", 65000, 20),
            ("Стол письменный", "Мебель", 80000, 2),
            ("Бумага A4 (пачка)", "Канцелярия", 2500, 300),
        ],
    )
    # (customer_id, product_id, quantity, status, created_at)
    orders = [
        (1, 1, 2, "paid", "2026-08-05"),
        (2, 3, 5, "shipped", "2026-08-12"),
        (3, 5, 40, "paid", "2026-08-20"),
        (1, 2, 3, "new", "2026-09-02"),
        (4, 4, 1, "paid", "2026-09-05"),
        (2, 1, 1, "new", "2026-09-10"),
        (3, 3, 2, "shipped", "2026-09-14"),
    ]
    for customer_id, product_id, qty, status, created_at in orders:
        price = conn.execute("SELECT price FROM products WHERE id = ?", (product_id,)).fetchone()[0]
        conn.execute(
            "INSERT INTO orders (customer_id, product_id, quantity, total, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (customer_id, product_id, qty, qty * price, status, created_at),
        )
