"""
Общий модуль для работы с PostgreSQL
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            balance INTEGER DEFAULT 0,
            last_bonus TEXT DEFAULT NULL,
            diamonds INTEGER DEFAULT 0,
            total_deposited INTEGER DEFAULT 0
        )
    """)
    # Миграция: добавляем новые колонки если их нет
    for col, default in [("diamonds", "0"), ("total_deposited", "0")]:
        try:
            c.execute(f"ALTER TABLE players ADD COLUMN {col} INTEGER DEFAULT {default}")
            conn.commit()
        except Exception:
            conn.rollback()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT,
            user_id BIGINT,
            bet_type TEXT,
            amount INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS session_stats (
            user_id BIGINT PRIMARY KEY,
            session_bet INTEGER DEFAULT 0,
            session_win INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    print("✅ БД инициализирована")

def get_player(user_id, name=None):
    conn = get_conn()
    c = conn.cursor()
    if name:
        c.execute(
            "INSERT INTO players (user_id, name, balance) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING",
            (user_id, name, 0)
        )
        conn.commit()
    c.execute("SELECT user_id, name, balance, last_bonus, diamonds, total_deposited FROM players WHERE user_id=%s", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_balance(user_id, delta):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET balance = balance + %s WHERE user_id=%s", (delta, user_id))
    conn.commit()
    conn.close()

def set_balance(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET balance=%s WHERE user_id=%s", (amount, user_id))
    conn.commit()
    conn.close()

def set_last_bonus(user_id, date_str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET last_bonus=%s WHERE user_id=%s", (date_str, user_id))
    conn.commit()
    conn.close()

def add_diamonds(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET diamonds = diamonds + %s WHERE user_id=%s", (amount, user_id))
    conn.commit()
    conn.close()

def get_diamonds(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT diamonds FROM players WHERE user_id=%s", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_total_deposited(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET total_deposited = total_deposited + %s WHERE user_id=%s", (amount, user_id))
    conn.commit()
    conn.close()

def add_bet(chat_id, user_id, bet_type, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO bets (chat_id, user_id, bet_type, amount) VALUES (%s,%s,%s,%s)",
              (chat_id, user_id, bet_type, amount))
    conn.commit()
    conn.close()

def get_bets(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, bet_type, amount FROM bets WHERE chat_id=%s", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def clear_bets(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM bets WHERE chat_id=%s", (chat_id,))
    conn.commit()
    conn.close()

def get_top(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name, diamonds FROM players ORDER BY diamonds DESC LIMIT %s", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def session_add_bet(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO session_stats (user_id, session_bet, session_win) VALUES (%s,0,0) ON CONFLICT (user_id) DO NOTHING", (user_id,))
    c.execute("UPDATE session_stats SET session_bet = session_bet + %s WHERE user_id=%s", (amount, user_id))
    conn.commit()
    conn.close()

def session_add_win(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO session_stats (user_id, session_bet, session_win) VALUES (%s,0,0) ON CONFLICT (user_id) DO NOTHING", (user_id,))
    c.execute("UPDATE session_stats SET session_win = session_win + %s WHERE user_id=%s", (amount, user_id))
    conn.commit()
    conn.close()

def session_reset(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO session_stats (user_id, session_bet, session_win) VALUES (%s,0,0) ON CONFLICT (user_id) DO NOTHING", (user_id,))
    c.execute("UPDATE session_stats SET session_bet=0, session_win=0 WHERE user_id=%s", (user_id,))
    conn.commit()
    conn.close()


