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
            total_deposited INTEGER DEFAULT 0,
            subscribed BOOLEAN DEFAULT FALSE,
            referred_by BIGINT DEFAULT NULL,
            referral_count INTEGER DEFAULT 0
        )
    """)
    # Миграция: добавляем новые колонки если их нет
    for col, default in [("diamonds", "0"), ("total_deposited", "0"), ("subscribed", "FALSE"), ("referred_by", "NULL"), ("referral_count", "0")]:
        try:
            if default == "FALSE":
                c.execute(f"ALTER TABLE players ADD COLUMN {col} BOOLEAN DEFAULT {default}")
            elif default == "NULL":
                c.execute(f"ALTER TABLE players ADD COLUMN {col} BIGINT DEFAULT NULL")
            else:
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
    init_promos()
    print("✅ БД инициализирована")

def add_silver(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET diamonds = diamonds + %s WHERE user_id=%s", (amount, user_id))
    conn.commit()
    conn.close()

def get_silver(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT diamonds FROM players WHERE user_id=%s", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

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

def get_subscribed(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT subscribed FROM players WHERE user_id=%s", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row[0]) if row else False

def set_subscribed(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET subscribed=TRUE WHERE user_id=%s", (user_id,))
    conn.commit()
    conn.close()

def apply_referral(new_user_id, referrer_id, bonus=15):
    """
    Привязывает реферала и начисляет бонус обоим.
    Возвращает True если успешно, False если уже был реферер.
    """
    conn = get_conn()
    c = conn.cursor()
    # Проверяем что у нового игрока ещё нет реферера
    c.execute("SELECT referred_by FROM players WHERE user_id=%s", (new_user_id,))
    row = c.fetchone()
    if not row or row[0] is not None:
        conn.close()
        return False
    # Нельзя пригласить самого себя
    if new_user_id == referrer_id:
        conn.close()
        return False
    # Привязываем и начисляем бонусы
    c.execute("UPDATE players SET referred_by=%s, balance=balance+%s WHERE user_id=%s",
              (referrer_id, bonus, new_user_id))
    c.execute("UPDATE players SET balance=balance+%s, referral_count=referral_count+1 WHERE user_id=%s",
              (bonus, referrer_id))
    conn.commit()
    conn.close()
    return True

def get_referral_count(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT referral_count FROM players WHERE user_id=%s", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

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

def init_promos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            silver INTEGER DEFAULT 0,
            gold INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            deposit_bonus_percent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS promo_uses (
            code TEXT,
            user_id BIGINT,
            deposit_used BOOLEAN DEFAULT FALSE,
            PRIMARY KEY (code, user_id)
        )
    """)
    # Миграции для существующих таблиц
    for col, definition in [
        ("deposit_bonus_percent", "INTEGER DEFAULT 0"),
        ("deposit_used", "BOOLEAN DEFAULT FALSE"),
    ]:
        try:
            c.execute(f"ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS {col} {definition}")
            c.execute(f"ALTER TABLE promo_uses ADD COLUMN IF NOT EXISTS {col} {definition}")
            conn.commit()
        except Exception:
            conn.rollback()
    conn.commit()
    conn.close()

def create_promo(code, silver=0, gold=0, max_uses=1, deposit_bonus_percent=0):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO promo_codes (code, silver, gold, max_uses, used_count, deposit_bonus_percent)
        VALUES (%s, %s, %s, %s, 0, %s)
        ON CONFLICT (code) DO UPDATE
            SET silver=%s, gold=%s, max_uses=%s, used_count=0, deposit_bonus_percent=%s
    """, (code, silver, gold, max_uses, deposit_bonus_percent,
          silver, gold, max_uses, deposit_bonus_percent))
    conn.commit()
    conn.close()

def get_active_deposit_promo(user_id):
    """Возвращает (code, percent) если у игрока есть неиспользованный депозит-промо, иначе None."""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT pu.code, pc.deposit_bonus_percent
            FROM promo_uses pu
            JOIN promo_codes pc ON pu.code = pc.code
            WHERE pu.user_id = %s
              AND pc.deposit_bonus_percent > 0
              AND pu.deposit_used = FALSE
            LIMIT 1
        """, (user_id,))
        row = c.fetchone()
    except Exception:
        conn.rollback()
        row = None
    conn.close()
    return row

def consume_deposit_promo(user_id):
    """Сжигает депозит-промо игрока. Возвращает процент бонуса или 0."""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT pu.code, pc.deposit_bonus_percent
            FROM promo_uses pu
            JOIN promo_codes pc ON pu.code = pc.code
            WHERE pu.user_id = %s
              AND pc.deposit_bonus_percent > 0
              AND pu.deposit_used = FALSE
            LIMIT 1
        """, (user_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return 0
        code, percent = row
        c.execute(
            "UPDATE promo_uses SET deposit_used = TRUE WHERE user_id=%s AND code=%s",
            (user_id, code)
        )
        conn.commit()
        conn.close()
        return percent
    except Exception:
        conn.rollback()
        conn.close()
        return 0

def delete_promo(code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM promo_codes WHERE code=%s", (code,))
    c.execute("DELETE FROM promo_uses WHERE code=%s", (code,))
    conn.commit()
    conn.close()

def list_promos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT code, silver, gold, max_uses, used_count, deposit_bonus_percent FROM promo_codes ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def use_promo(code, user_id):
    """
    Возвращает:
      ('ok', silver, gold)         — фишки сразу начислены
      ('ok_deposit', percent, 0)   — депозит-промо активировано, ждёт пополнения
      ('already_used', 0, 0)       — уже использовал
      ('not_found', 0, 0)          — промокод не найден
      ('limit', 0, 0)              — лимит активаций исчерпан
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT silver, gold, max_uses, used_count, deposit_bonus_percent FROM promo_codes WHERE code=%s", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return ('not_found', 0, 0)
    silver, gold, max_uses, used_count, deposit_bonus_percent = row
    if used_count >= max_uses:
        conn.close()
        return ('limit', 0, 0)
    c.execute("SELECT 1 FROM promo_uses WHERE code=%s AND user_id=%s", (code, user_id))
    if c.fetchone():
        conn.close()
        return ('already_used', 0, 0)
    # Активируем — deposit_used=FALSE для депозит-промо, TRUE для обычных (уже отработали)
    is_deposit_promo = deposit_bonus_percent > 0
    c.execute(
        "INSERT INTO promo_uses (code, user_id, deposit_used) VALUES (%s, %s, %s)",
        (code, user_id, not is_deposit_promo)
    )
    c.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code=%s", (code,))
    if not is_deposit_promo:
        if silver > 0:
            c.execute("UPDATE players SET balance = balance + %s WHERE user_id=%s", (silver, user_id))
        if gold > 0:
            c.execute("UPDATE players SET diamonds = diamonds + %s WHERE user_id=%s", (gold, user_id))
    conn.commit()
    conn.close()
    if is_deposit_promo:
        return ('ok_deposit', deposit_bonus_percent, 0)
    return ('ok', silver, gold)

def session_reset(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO session_stats (user_id, session_bet, session_win) VALUES (%s,0,0) ON CONFLICT (user_id) DO NOTHING", (user_id,))
    c.execute("UPDATE session_stats SET session_bet=0, session_win=0 WHERE user_id=%s", (user_id,))
    conn.commit()
    conn.close()
