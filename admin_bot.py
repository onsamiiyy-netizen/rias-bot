"""
🔐 Админ-бот для управления выводами
Доступ только по секретной ссылке: t.me/БОТ?start=СЕКРЕТНЫЙ_КОД
"""

import telebot
import os
from db import get_player, update_balance
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

# =================== ЗАПУСК ===================
if __name__ == "__main__":
    print("🔐 Админ-бот запущен!")
    print(f"Ссылка для входа: t.me/<username_бота>?start={SECRET_CODE}")
    bot.infinity_polling()
