"""AI-фича: вопрос на естественном языке -> SQL -> ответ из базы."""
import os
import re

import anthropic

from db import SCHEMA, get_conn

MODEL = "claude-opus-5"

SYSTEM_PROMPT = f"""Ты помощник в ERP-системе. Переводи вопрос пользователя в ОДИН SQL-запрос для SQLite.

Схема базы:
{SCHEMA}

Правила:
- Только SELECT (или WITH ... SELECT). Никаких INSERT/UPDATE/DELETE/DROP.
- Даты хранятся как текст 'YYYY-MM-DD'; используй strftime/date для фильтров.
- Давай колонкам понятные псевдонимы на русском через AS "...".
- Ответь только SQL-запросом, без пояснений и без ```."""


def question_to_sql(question: str) -> str:
    """Спросить LLM и получить SQL-запрос."""
    client = anthropic.Anthropic()  # ключ берётся из ANTHROPIC_API_KEY в .env
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=2000,
        output_config={"effort": "low"},  # задача простая — экономим время и токены
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
        # если основная модель откажется отвечать, API сам попробует резервную
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise ValueError("Модель отказалась отвечать на этот вопрос")
    text = "".join(b.text for b in response.content if b.type == "text")
    return text.strip().strip("`").removeprefix("sql").strip()


def is_safe_select(sql: str) -> bool:
    """Защита: разрешаем только один SELECT-запрос."""
    cleaned = sql.strip().rstrip(";").lower()
    if ";" in cleaned:
        return False
    if not (cleaned.startswith("select") or cleaned.startswith("with")):
        return False
    forbidden = r"\b(insert|update|delete|drop|alter|create|attach|pragma|replace)\b"
    return re.search(forbidden, cleaned) is None


def ask(question: str) -> dict:
    """Полный цикл: вопрос -> SQL -> выполнение -> строки результата."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("Не задан ANTHROPIC_API_KEY в backend/.env")
    sql = question_to_sql(question)
    if not is_safe_select(sql):
        raise ValueError(f"Небезопасный запрос отклонён: {sql}")
    conn = get_conn(readonly=True)  # вторая линия защиты: БД открыта только на чтение
    try:
        rows = [dict(r) for r in conn.execute(sql).fetchmany(200)]
    finally:
        conn.close()
    return {"sql": sql, "rows": rows}
