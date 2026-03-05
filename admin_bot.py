"""
🔐 Админ-бот для управления выводами
Доступ только по секретной ссылке: t.me/БОТ?start=СЕКРЕТНЫЙ_КОД
"""

import telebot
import os
from db import get_player, update_balance, create_promo, delete_promo, list_promos
import traceback
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===================== НАСТРОЙКИ =====================
ADMIN_BOT_TOKEN = os.environ.get("ADMIN_BOT_TOKEN")
SECRET_CODE = "rias2024admin"  # секретный код для входа — измени на свой
# =====================================================

bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

# Авторизованные админы (кто вошёл по ссылке)
authorized_admins = set()

# =================== КОМАНДЫ ===================

@bot.message_handler(commands=["start"])
def cmd_start(msg):
    parts = msg.text.split()
    if len(parts) > 1 and parts[1] == SECRET_CODE:
        authorized_admins.add(msg.from_user.id)
        bot.send_message(msg.chat.id,
            "🔐 Доступ разрешён!\n\nДобро пожаловать в админ-панель.\n\nЗдесь будут приходить заявки на вывод от игроков.")
    else:
        bot.send_message(msg.chat.id, "⛔ Доступ запрещён.")

@bot.message_handler(commands=["stats"])
def cmd_stats(msg):
    if msg.from_user.id not in authorized_admins:
        bot.send_message(msg.chat.id, "⛔ Нет доступа.")
        return
    from db import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(balance) FROM players")
    row = c.fetchone()
    conn.close()
    players = row[0] or 0
    total = row[1] or 0
    bot.send_message(msg.chat.id,
        f"📊 Статистика:\n\nИгроков: {players}\nСуммарный баланс: {total} фишек")

# =================== ЗАЯВКИ НА ВЫВОД ===================

@bot.callback_query_handler(func=lambda c: c.data.startswith("wadmin_done_"))
def cb_done(call):
    if call.from_user.id not in authorized_admins:
        bot.answer_callback_query(call.id, "⛔ Нет доступа!")
        return
    bot.answer_callback_query(call.id)
    try:
        parts = call.data.split("_")
        user_id = int(parts[2])
        amount = int(parts[3])
        p = get_player(user_id)
        name = p[1] if p else str(user_id)
        bot.edit_message_text(
            f"✅ Выполнено!\n{name} получил {amount} ⭐",
            call.message.chat.id, call.message.message_id)
        try:
            # Уведомляем игрока через основной бот
            main_bot = telebot.TeleBot(os.environ.get("BOT_TOKEN"))
            main_bot.send_message(user_id, f"✅ Ваш вывод выполнен!\n💫 {amount} ⭐ Telegram Stars отправлены.")
        except Exception:
            pass
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("wadmin_reject_"))
def cb_reject(call):
    if call.from_user.id not in authorized_admins:
        bot.answer_callback_query(call.id, "⛔ Нет доступа!")
        return
    bot.answer_callback_query(call.id)
    try:
        parts = call.data.split("_")
        user_id = int(parts[2])
        amount = int(parts[3])
        update_balance(user_id, amount)
        p = get_player(user_id)
        name = p[1] if p else str(user_id)
        bot.edit_message_text(
            f"❌ Отклонено.\n{name} — {amount} фишек возвращены.",
            call.message.chat.id, call.message.message_id)
        try:
            main_bot = telebot.TeleBot(os.environ.get("BOT_TOKEN"))
            main_bot.send_message(user_id, f"❌ Заявка на вывод отклонена.\n💰 {amount} фишек возвращены на баланс.")
        except Exception:
            pass
    except Exception:
        traceback.print_exc()

# =================== ПРОМОКОДЫ ===================

@bot.message_handler(commands=["newdepositpromo"])
def cmd_newdepositpromo(msg):
    """
    Создать промокод на % к пополнению.
    Формат: /newdepositpromo КОД процент макс_активаций
    Пример: /newdepositpromo BONUS50 50 100
    """
    if msg.from_user.id not in authorized_admins:
        bot.send_message(msg.chat.id, "⛔ Нет доступа.")
        return
    parts = msg.text.split()
    if len(parts) != 4:
        bot.send_message(msg.chat.id,
            "❌ Неверный формат.\n\n"
            "Используй:\n<code>/newdepositpromo КОД процент активаций</code>\n\n"
            "Пример:\n/newdepositpromo BONUS50 50 100\n"
            "→ игрок активирует, следующее пополнение +50% бонусом (100 игроков)",
            parse_mode="HTML")
        return
    _, code, pct_str, uses_str = parts
    try:
        percent = int(pct_str)
        max_uses = int(uses_str)
        assert 1 <= percent <= 500 and max_uses >= 1
    except Exception:
        bot.send_message(msg.chat.id, "❌ Процент: 1–500, активации ≥ 1.")
        return
    code = code.upper()
    create_promo(code, silver=0, gold=0, max_uses=max_uses, deposit_bonus_percent=percent)
    bot.send_message(msg.chat.id,
        f"✅ Депозит-промокод создан!\n\n"
        f"🎟 Код: <code>{code}</code>\n"
        f"💹 Бонус к пополнению: +{percent}%\n"
        f"🔢 Активаций: {max_uses}\n\n"
        f"Игрок активирует промо → делает пополнение → получает +{percent}% сверху → промо сгорает.",
        parse_mode="HTML")

@bot.message_handler(commands=["newpromo"])
def cmd_newpromo(msg):
    """
    Создать промокод.
    Формат: /newpromo КОД серебро золото макс_активаций
    Пример: /newpromo SUMMER100 200 0 50
            /newpromo GOLDBOOST 0 100 10
    """
    if msg.from_user.id not in authorized_admins:
        bot.send_message(msg.chat.id, "⛔ Нет доступа.")
        return
    parts = msg.text.split()
    if len(parts) != 5:
        bot.send_message(msg.chat.id,
            "❌ Неверный формат.\n\n"
            "Используй:\n<code>/newpromo КОД серебро золото макс_активаций</code>\n\n"
            "Примеры:\n"
            "/newpromo SUMMER100 200 0 50 — 200 ⚪ серебряных, 50 активаций\n"
            "/newpromo GOLDVIP 0 100 10 — 100 🟡 золотых, 10 активаций\n"
            "/newpromo WELCOME 100 50 999 — 100 ⚪ + 50 🟡, 999 активаций",
            parse_mode="HTML")
        return
    _, code, silver_str, gold_str, uses_str = parts
    try:
        silver = int(silver_str)
        gold = int(gold_str)
        max_uses = int(uses_str)
        assert silver >= 0 and gold >= 0 and max_uses >= 1
    except Exception:
        bot.send_message(msg.chat.id, "❌ Серебро, золото и активации — целые числа ≥ 0 (активации ≥ 1).")
        return
    code = code.upper()
    create_promo(code, silver=silver, gold=gold, max_uses=max_uses)
    parts_desc = []
    if silver: parts_desc.append(f"{silver} ⚪ серебряных")
    if gold:   parts_desc.append(f"{gold} 🟡 золотых")
    reward_text = " + ".join(parts_desc) if parts_desc else "ничего (0 фишек)"
    bot.send_message(msg.chat.id,
        f"✅ Промокод создан!\n\n"
        f"🎟 Код: <code>{code}</code>\n"
        f"💰 Награда: {reward_text}\n"
        f"🔢 Активаций: {max_uses}",
        parse_mode="HTML")

@bot.message_handler(commands=["delpromo"])
def cmd_delpromo(msg):
    """Удалить промокод. Формат: /delpromo КОД"""
    if msg.from_user.id not in authorized_admins:
        bot.send_message(msg.chat.id, "⛔ Нет доступа.")
        return
    parts = msg.text.split()
    if len(parts) != 2:
        bot.send_message(msg.chat.id, "Формат: /delpromo КОД")
        return
    code = parts[1].upper()
    delete_promo(code)
    bot.send_message(msg.chat.id, f"🗑 Промокод <code>{code}</code> удалён.", parse_mode="HTML")

@bot.message_handler(commands=["promos"])
def cmd_promos(msg):
    """Список всех промокодов."""
    if msg.from_user.id not in authorized_admins:
        bot.send_message(msg.chat.id, "⛔ Нет доступа.")
        return
    rows = list_promos()
    if not rows:
        bot.send_message(msg.chat.id, "📋 Промокодов пока нет.")
        return
    text = "📋 <b>Активные промокоды:</b>\n\n"
    for code, silver, gold, max_uses, used_count, deposit_pct in rows:
        if deposit_pct > 0:
            reward = f"+{deposit_pct}% к депозиту"
            icon = "💹"
        else:
            parts_desc = []
            if silver: parts_desc.append(f"{silver} ⚪")
            if gold:   parts_desc.append(f"{gold} 🟡")
            reward = " + ".join(parts_desc) if parts_desc else "0"
            icon = "🎟"
        text += f"{icon} <code>{code}</code> — {reward} | {used_count}/{max_uses} активаций\n"
    text += "\nУдалить: /delpromo КОД"
    bot.send_message(msg.chat.id, text, parse_mode="HTML")

# =================== ЗАПУСК ===================
if __name__ == "__main__":
    print("🔐 Админ-бот запущен!")
    print(f"Ссылка для входа: t.me/<username_бота>?start={SECRET_CODE}")
    bot.infinity_polling()
