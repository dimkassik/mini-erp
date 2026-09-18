"""REST API мини-ERP. Запуск: uvicorn main:app --reload"""
import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()  # читаем backend/.env (там ANTHROPIC_API_KEY)

import ai  # noqa: E402
from db import get_conn, init_db  # noqa: E402

app = FastAPI(title="Mini AI ERP")
app.add_middleware(  # разрешаем фронтенду (другой порт) ходить на API
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
init_db()


# ---------- Модели входных данных (что присылает фронт) ----------

class ProductIn(BaseModel):
    name: str
    category: str = ""
    price: float
    stock: int = 0


class CustomerIn(BaseModel):
    name: str
    email: str = ""
    city: str = ""


class OrderIn(BaseModel):
    customer_id: int
    product_id: int
    quantity: int


class Question(BaseModel):
    question: str


def rows(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# ---------- Товары ----------

@app.get("/api/products")
def list_products():
    return rows("SELECT * FROM products ORDER BY id")


@app.post("/api/products")
def create_product(p: ProductIn):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
        (p.name, p.category, p.price, p.stock),
    )
    conn.commit()
    conn.close()
    return {"id": cur.lastrowid}


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Клиенты ----------

@app.get("/api/customers")
def list_customers():
    return rows("SELECT * FROM customers ORDER BY id")


@app.post("/api/customers")
def create_customer(c: CustomerIn):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO customers (name, email, city) VALUES (?, ?, ?)", (c.name, c.email, c.city)
    )
    conn.commit()
    conn.close()
    return {"id": cur.lastrowid}


# ---------- Заказы ----------

@app.get("/api/orders")
def list_orders():
    return rows(
        """SELECT o.id, c.name AS customer, p.name AS product, o.quantity, o.total,
                  o.status, o.created_at
           FROM orders o
           JOIN customers c ON c.id = o.customer_id
           JOIN products  p ON p.id = o.product_id
           ORDER BY o.id DESC"""
    )


@app.post("/api/orders")
def create_order(o: OrderIn):
    """Бизнес-логика: проверяем остаток, списываем со склада, считаем сумму."""
    conn = get_conn()
    try:
        product = conn.execute("SELECT * FROM products WHERE id = ?", (o.product_id,)).fetchone()
        if product is None:
            raise HTTPException(404, "Товар не найден")
        if product["stock"] < o.quantity:
            raise HTTPException(400, f"Недостаточно на складе: осталось {product['stock']}")
        cur = conn.execute(
            "INSERT INTO orders (customer_id, product_id, quantity, total) VALUES (?, ?, ?, ?)",
            (o.customer_id, o.product_id, o.quantity, o.quantity * product["price"]),
        )
        conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (o.quantity, o.product_id))
        conn.commit()
        return {"id": cur.lastrowid}
    finally:
        conn.close()


# ---------- Дашборд ----------

@app.get("/api/stats")
def stats():
    return {
        "revenue": rows("SELECT COALESCE(SUM(total), 0) AS v FROM orders WHERE status != 'new'")[0]["v"],
        "orders": rows("SELECT COUNT(*) AS v FROM orders")[0]["v"],
        "customers": rows("SELECT COUNT(*) AS v FROM customers")[0]["v"],
        "low_stock": rows("SELECT name, stock FROM products WHERE stock < 5 ORDER BY stock"),
    }


# ---------- AI: вопрос к базе ----------

@app.post("/api/ask")
def ask(q: Question):
    try:
        return ai.ask(q.question)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except anthropic.AuthenticationError:
        raise HTTPException(401, "Неверный ANTHROPIC_API_KEY")
    except anthropic.RateLimitError:
        raise HTTPException(429, "Лимит запросов к LLM, попробуйте позже")
    except anthropic.APIError as e:
        raise HTTPException(502, f"Ошибка LLM: {e}")
    except Exception as e:  # например, LLM сгенерировала SQL с ошибкой
        raise HTTPException(400, f"Ошибка выполнения SQL: {e}")
