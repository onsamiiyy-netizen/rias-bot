"""
🎰 Telegram Рулетка Бот — Мультиплеер с кнопками
Требования: pip install pyTelegramBotAPI
Запуск: python roulette_bot_final.py
"""

import telebot
import os
import random
import time
from db import (init_db, get_player, update_balance, set_balance, set_last_bonus,
    add_bet, get_bets, clear_bets, get_top, session_add_bet, session_add_win, session_reset,
    add_silver, get_silver, add_total_deposited, use_promo,
    get_active_deposit_promo, consume_deposit_promo,
    get_subscribed, set_subscribed, apply_referral, get_referral_count)
import traceback

# Патч: глушим неважную ошибку "message is not modified"
_original_print_exc = traceback.print_exc
def _filtered_print_exc(*args, **kwargs):
    import sys
    import io
    buf = io.StringIO()
    import traceback as _tb
    _tb.print_exc(file=buf)
    s = buf.getvalue()
    if "message is not modified" not in s and "Bad Request: query is too old" not in s:
        print(s, end='', file=sys.stderr)
traceback.print_exc = _filtered_print_exc

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# ID или @username канала для обязательной подписки
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "@RiasChanel")
SUBSCRIBE_BONUS = 15  # серебряных за подписку
REFERRAL_BONUS = 15   # серебряных рефереру и новичку
# =====================================================

bot = telebot.TeleBot(BOT_TOKEN)

def safe_edit(chat_id, message_id, text, **kwargs):
    """Редактирует сообщение, игнорируя ошибку 'message is not modified'"""
    try:
        bot.edit_message_text(text, chat_id, message_id, **kwargs)
    except Exception as e:
        if "message is not modified" not in str(e):
            traceback.print_exc()

STARTING_BALANCE = 0

RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

# =================== СЕССИЯ / ПОДКРУТКА ===================

DRAIN_PROFIT_THRESHOLD = 75  # сколько фишек прибыли сверх депозита чтобы включился слив
DRAIN_CHANCE = 0.30           # шанс подставить мину в режиме слива (30%)

def is_draining(user_id):
    """Включает слив если игрок выиграл больше чем задепозитил на DRAIN_PROFIT_THRESHOLD фишек"""
    p = get_player(user_id)
    if not p:
        return False
    balance = p[2]
    total_deposited = p[5] if len(p) > 5 else 0
    # Слив только если баланс превышает депозит на 75+ фишек
    if total_deposited == 0:
        return False
    profit = balance - total_deposited
    return profit >= DRAIN_PROFIT_THRESHOLD














# =================== УТИЛИТЫ ===================

def get_color(n):
    if n == 0: return "🟢"
    if n in RED_NUMBERS: return "🔴"
    return "⚫"

def calculate_win(bet_type, amount, result):
    if bet_type == "red":
        if result in RED_NUMBERS: return amount * 2
    elif bet_type == "black":
        if result in BLACK_NUMBERS: return amount * 2
    elif bet_type == "green":
        if result == 0: return amount * 14
    elif bet_type == "even":
        if result != 0 and result % 2 == 0: return amount * 2
    elif bet_type == "odd":
        if result % 2 == 1: return amount * 2
    elif bet_type == "1-18":
        if 1 <= result <= 18: return amount * 2
    elif bet_type == "19-36":
        if 19 <= result <= 36: return amount * 2
    else:
        try:
            if int(bet_type) == result: return amount * 35
        except: pass
    return 0

LABEL_MAP = {
    "red": "🔴 Красное", "black": "⚫ Чёрное", "green": "🟢 Зеро",
    "even": "2️⃣ Чётное", "odd": "1️⃣ Нечётное",
    "1-18": "⬇️ 1–18", "19-36": "⬆️ 19–36"
}

def bet_label(bet_type):
    return LABEL_MAP.get(bet_type, f"🔢 Число {bet_type}")

# =================== КЛАВИАТУРЫ ===================

def main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🎰 Играть"), KeyboardButton("💰 Баланс"))
    kb.row(KeyboardButton("🎁 Бонус"), KeyboardButton("🏆 Топ игроков"))
    kb.row(KeyboardButton("📋 Задания"), KeyboardButton("🎟 Промокод"))
    kb.row(KeyboardButton("👥 Рефералы"), KeyboardButton("📖 Правила"))
    kb.row(KeyboardButton("💳 Пополнить"), KeyboardButton("💸 Вывести"))
    return kb

def bet_type_keyboard():
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("🔴 Красное x2",  callback_data="bettype_red"),
        InlineKeyboardButton("⚫ Чёрное x2",   callback_data="bettype_black"),
        InlineKeyboardButton("🟢 Зеро x14",    callback_data="bettype_green"),
    )
    kb.add(
        InlineKeyboardButton("Чётное x2",      callback_data="bettype_even"),
        InlineKeyboardButton("Нечётное x2",    callback_data="bettype_odd"),
    )
    kb.add(
        InlineKeyboardButton("1-18 x2",        callback_data="bettype_118"),
        InlineKeyboardButton("19-36 x2",       callback_data="bettype_1936"),
    )
    kb.add(InlineKeyboardButton("🔢 Конкретное число x35", callback_data="bettype_number"))
    kb.add(InlineKeyboardButton("🎰 Крутить рулетку!", callback_data="spin"))
    return kb

def amount_keyboard(bet_type, currency="silver"):
    kb = InlineKeyboardMarkup(row_width=4)
    kb.add(
        InlineKeyboardButton("5",    callback_data=f"amt_{bet_type}_{currency}_5"),
        InlineKeyboardButton("10",   callback_data=f"amt_{bet_type}_{currency}_10"),
        InlineKeyboardButton("15",   callback_data=f"amt_{bet_type}_{currency}_15"),
        InlineKeyboardButton("25",   callback_data=f"amt_{bet_type}_{currency}_25"),
    )
    kb.add(
        InlineKeyboardButton("30",   callback_data=f"amt_{bet_type}_{currency}_30"),
        InlineKeyboardButton("50",   callback_data=f"amt_{bet_type}_{currency}_50"),
        InlineKeyboardButton("100",  callback_data=f"amt_{bet_type}_{currency}_100"),
        InlineKeyboardButton("200",  callback_data=f"amt_{bet_type}_{currency}_200"),
    )
    kb.add(
        InlineKeyboardButton("300",  callback_data=f"amt_{bet_type}_{currency}_300"),
        InlineKeyboardButton("500",  callback_data=f"amt_{bet_type}_{currency}_500"),
        InlineKeyboardButton("1000", callback_data=f"amt_{bet_type}_{currency}_1000"),
        InlineKeyboardButton("ALL IN", callback_data=f"amt_{bet_type}_{currency}_allin"),
    )
    kb.add(InlineKeyboardButton("✏️ Ввести ставку", callback_data=f"amt_{bet_type}_{currency}_custom"))
    kb.add(InlineKeyboardButton("Назад", callback_data=f"cur_{bet_type}_back"))
    return kb

def currency_keyboard(bet_type):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⚪ Серебряные", callback_data=f"cur_{bet_type}_silver"),
        InlineKeyboardButton("🟡 Золотые", callback_data=f"cur_{bet_type}_gold"),
    )
    kb.add(InlineKeyboardButton("Назад", callback_data="back_to_bets"))
    return kb

def number_keyboard():
    kb = InlineKeyboardMarkup(row_width=6)
    buttons = [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(37)]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("Назад", callback_data="back_to_bets"))
    return kb

def after_bet_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Ещё ставку", callback_data="back_to_bets"),
        InlineKeyboardButton("🎰 Крутить!", callback_data="spin"),
    )
    return kb

def new_round_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎰 Новая ставка", callback_data="back_to_bets"))
    return kb

# =================== КОМАНДЫ ===================

@bot.message_handler(commands=["start"])
def cmd_start(msg):
    print(f"[DEBUG] /start от {msg.from_user.id}")
    uid = msg.from_user.id
    is_new = get_player(uid) is None
    get_player(uid, msg.from_user.first_name)

    # Обрабатываем реферальную ссылку
    parts = msg.text.split()
    if len(parts) > 1 and parts[1].startswith("ref"):
        try:
            referrer_id = int(parts[1][3:])
            if is_new and apply_referral(uid, referrer_id, REFERRAL_BONUS):
                # Уведомляем реферера
                try:
                    bot.send_message(referrer_id,
                        f"👥 По вашей ссылке зарегистрировался новый игрок!\n"
                        f"🎁 Вам начислено +{REFERRAL_BONUS} ⚪ серебряных.")
                except Exception:
                    pass
                bot.send_message(msg.chat.id,
                    f"🎰 Добро пожаловать в Казино Рулетку!\n\n"
                    f"🎁 Вы зарегистрировались по реферальной ссылке и получили +{REFERRAL_BONUS} ⚪ серебряных!\n\n"
                    f"Крути рулетку, делай ставки и выигрывай фишки!\nИспользуй кнопки внизу",
                    reply_markup=main_keyboard())
                return
        except Exception:
            pass

    bot.send_message(msg.chat.id,
        "🎰 Добро пожаловать в Казино Рулетку!\n\nКрути рулетку, делай ставки и выигрывай фишки!\nИспользуй кнопки внизу",
        reply_markup=main_keyboard())

def game_select_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎰 Рулетка", callback_data="game_roulette"),
        InlineKeyboardButton("💣 Мины",    callback_data="game_mines"),
    )
    return kb

@bot.message_handler(func=lambda m: m.text == "🎰 Играть")
def msg_play(msg):
    print(f"[DEBUG] Играть от {msg.from_user.id}")
    get_player(msg.from_user.id, msg.from_user.first_name)
    bot.send_message(msg.chat.id,
        "🎮 Выберите игру:",
        reply_markup=game_select_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "game_roulette")
def cb_game_roulette(call):
    bot.answer_callback_query(call.id)
    bets = get_bets(call.message.chat.id)
    bet_info = _bets_text(bets)
    bot.edit_message_text(
        f"🎰 Рулетка — выберите тип ставки:{bet_info}",
        call.message.chat.id, call.message.message_id,
        reply_markup=bet_type_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "game_mines")
def cb_game_mines(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "💣 Игра Мины!\n\nВыберите размер поля:",
        call.message.chat.id, call.message.message_id,
        reply_markup=mines_start_keyboard())

@bot.message_handler(func=lambda m: m.text == "💰 Баланс")
def msg_balance(msg):
    p = get_player(msg.from_user.id, msg.from_user.first_name)
    gold = p[2]
    diamonds = p[4] if len(p) > 4 else 0
    total_deposited = p[5] if len(p) > 5 else 0
    bot.send_message(msg.chat.id,
        f"💰 {p[1]}, ваш баланс:\n\n"
        f"⚪ Серебряные: {gold} (для игры)\n"
        f"🟡 Золотые: {diamonds} (для вывода)\n\n"
        f"📥 Задепонировано всего: {total_deposited} / 75 🟡")

@bot.message_handler(func=lambda m: m.text == "🏆 Топ игроков")
def msg_top(msg):
    rows = get_top()
    medals = ["👑", "⚪", "🔥", "⚡", "🌟", "✨", "💫", "🎯", "🎖️", "🏅"]
    text = "🏆 Таблица лидеров:\n\n"
    for i, (name, bal) in enumerate(rows):
        m = medals[i] if i < len(medals) else f"{i+1}."
        text += f"{m} {name} — {bal} 🟡\n"
    bot.send_message(msg.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "🎁 Бонус")
def msg_bonus(msg):
    from datetime import date
    today = str(date.today())
    p = get_player(msg.from_user.id, msg.from_user.first_name)
    if p[3] == today:
        bot.send_message(msg.chat.id, "Вы уже получили бонус сегодня. Возвращайтесь завтра!")
        return
    bonus = 15
    update_balance(msg.from_user.id, bonus)
    set_last_bonus(msg.from_user.id, today)
    bot.send_message(msg.chat.id,
        f"🎁 Ежедневный бонус!\nВы получили {bonus} ⚪ серебряных!\nНовый баланс: {p[2] + bonus} ⚪")

@bot.message_handler(func=lambda m: m.text == "📖 Правила")
def msg_rules(msg):
    bot.send_message(msg.chat.id,
        "📖 Правила рулетки:\n\n"
        "🔴 Красное / Чёрное — выплата x2\n"
        "🟢 Зеро (0) — выплата x14\n"
        "Чётное / Нечётное — выплата x2\n"
        "1–18 / 19–36 — выплата x2\n"
        "🔢 Конкретное число — выплата x35\n\n"
        "🎁 Ежедневный бонус: 15 фишек\n"
        "Можно делать несколько ставок за раунд\n")


# =================== CALLBACK ===================

def _bets_text(bets):
    if not bets:
        return ""
    text = "\n\nТекущие ставки:\n"
    for uid, btype, amt in bets:
        p = get_player(uid)
        name = p[1] if p else "Игрок"
        text += f"• {name}: {amt} фишек на {bet_label(btype)}\n"
    return text

@bot.callback_query_handler(func=lambda c: c.data == "back_to_bets")
def cb_back(call):
    print(f"[DEBUG] cb_back")
    bot.answer_callback_query(call.id)
    try:
        bets = get_bets(call.message.chat.id)
        bot.edit_message_text(
            f"🎰 Рулетка — выберите тип ставки:{_bets_text(bets)}",
            call.message.chat.id, call.message.message_id,
            reply_markup=bet_type_keyboard())
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data == "bettype_number")
def cb_number_menu(call):
    print(f"[DEBUG] cb_number_menu")
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(
            "🔢 Выберите число (0–36):",
            call.message.chat.id, call.message.message_id,
            reply_markup=number_keyboard())
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("bettype_"))
def cb_bet_type(call):
    print(f"[DEBUG] cb_bet_type: {call.data}")
    bot.answer_callback_query(call.id)
    try:
        bet_type = call.data[len("bettype_"):]
        if bet_type == "118": bet_type = "1-18"
        if bet_type == "1936": bet_type = "19-36"
        p = get_player(call.from_user.id, call.from_user.first_name)
        diamonds = get_silver(call.from_user.id)
        bot.edit_message_text(
            f"🎰 {bet_label(bet_type)}\n\n⚪ Серебряные: {p[2]}\n🟡 Золотые: {diamonds}\n\nВыберите валюту для ставки:",
            call.message.chat.id, call.message.message_id,
            reply_markup=currency_keyboard(bet_type))
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("num_"))
def cb_number_bet(call):
    print(f"[DEBUG] cb_number_bet: {call.data}")
    bot.answer_callback_query(call.id)
    try:
        bet_type = call.data[len("num_"):]
        p = get_player(call.from_user.id, call.from_user.first_name)
        diamonds = get_silver(call.from_user.id)
        bot.edit_message_text(
            f"🎰 {bet_label(bet_type)}\n\n⚪ Серебряные: {p[2]}\n🟡 Золотые: {diamonds}\n\nВыберите валюту для ставки:",
            call.message.chat.id, call.message.message_id,
            reply_markup=currency_keyboard(bet_type))
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("cur_"))
def cb_currency(call):
    bot.answer_callback_query(call.id)
    try:
        parts = call.data.split("_")
        currency = parts[-1]
        bet_type = "_".join(parts[1:-1])

        if currency == "back":
            bets = get_bets(call.message.chat.id)
            bot.edit_message_text(
                f"🎰 Рулетка — выберите тип ставки:{_bets_text(bets)}",
                call.message.chat.id, call.message.message_id,
                reply_markup=bet_type_keyboard())
            return

        p = get_player(call.from_user.id, call.from_user.first_name)
        diamonds = get_silver(call.from_user.id)
        cur_label = "⚪ Серебряные" if currency == "silver" else "🟡 Золотые"
        balance = p[2] if currency == "silver" else diamonds
        bot.edit_message_text(
            f"🟡 {bet_label(bet_type)} | {cur_label}\n\nБаланс: {balance}\nВыберите сумму ставки:",
            call.message.chat.id, call.message.message_id,
            reply_markup=amount_keyboard(bet_type, currency))
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("amt_"))
def cb_amount(call):
    print(f"[DEBUG] cb_amount: {call.data}")
    bot.answer_callback_query(call.id)
    try:
        parts = call.data.split("_")
        val = parts[-1]
        currency = parts[-2]
        bet_type = "_".join(parts[1:-2])

        if val == "custom":
            custom_bet_waiting[call.from_user.id] = {"bet_type": bet_type, "currency": currency, "chat_id": call.message.chat.id, "msg_id": call.message.message_id}
            bot.edit_message_text(
                f"✏️ Введите сумму ставки (минимум 5):",
                call.message.chat.id, call.message.message_id)
            return

        p = get_player(call.from_user.id, call.from_user.first_name)
        diamonds = get_silver(call.from_user.id)
        balance = p[2] if currency == "silver" else diamonds
        amount = balance if val == "allin" else int(val)

        if amount < 5:
            bot.answer_callback_query(call.id, "Минимальная ставка 5!")
            return
        if amount <= 0:
            bot.answer_callback_query(call.id, "У вас нет средств!")
            return
        if amount > balance:
            cur_label = "⚪" if currency == "silver" else "🟡"
            bot.answer_callback_query(call.id, f"Недостаточно {cur_label}! Баланс: {balance}")
            return

        if currency == "silver":
            update_balance(call.from_user.id, -amount)
        else:
            add_silver(call.from_user.id, -amount)

        add_bet(call.message.chat.id, call.from_user.id, bet_type, amount)
        session_add_bet(call.from_user.id, amount)
        p_new = get_player(call.from_user.id)
        cur_icon = "⚪" if currency == "silver" else "🟡"

        bot.edit_message_text(
            f"Ставка принята!\n{p_new[1]}: {amount} {cur_icon} на {bet_label(bet_type)}\n⚪ Серебряных: {p_new[2]} | 🟡 Золотых: {get_silver(call.from_user.id)}\n\nЖдём других или крутим?",
            call.message.chat.id, call.message.message_id,
            reply_markup=after_bet_keyboard())
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data == "spin")
def cb_spin(call):
    print(f"[DEBUG] cb_spin")
    try:
        bot.answer_callback_query(call.id)
        bets = get_bets(call.message.chat.id)
        if not bets:
            bot.send_message(call.message.chat.id, "Никто не сделал ставку!")
            return

        total_bets = sum(a for _, _, a in bets)
        players_in = len(set(uid for uid, _, _ in bets))

        bot.edit_message_text(
            f"🎰 Рулетка крутится...\nИгроков: {players_in} | В банке: {total_bets}\n\nЖдите...",
            call.message.chat.id, call.message.message_id)

        time.sleep(2)

        # Недокрут: 70% шанс что казино выигрывает
        CASINO_WIN_CHANCE = 0.50

        result = random.randint(0, 36)

        if random.random() < CASINO_WIN_CHANCE:
            bet_types = set(btype for _, btype, _ in bets)
            for _ in range(100):
                candidate = random.randint(0, 36)
                if all(calculate_win(btype, 1, candidate) == 0 for btype in bet_types):
                    result = candidate
                    break

        color = get_color(result)

        results = {}
        for uid, btype, amt in bets:
            win = calculate_win(btype, amt, result)
            results[uid] = results.get(uid, 0) + win

        winners_text = ""
        losers_text = ""

        for uid, total_win in results.items():
            p = get_player(uid)
            if not p: continue
            if total_win > 0:
                add_silver(uid, total_win)
                new_silver = get_silver(uid)
                session_add_win(uid, total_win)
                winners_text += f"🏆 {p[1]}: +{total_win} 🟡 (золотых: {new_silver})\n"
            else:
                losers_text += f"💸 {p[1]}: проиграл\n"

        clear_bets(call.message.chat.id)

        text = f"🎯 Результат: {color} {result}\n\n"
        if winners_text: text += f"Победители:\n{winners_text}\n"
        if losers_text:  text += f"Проигравшие:\n{losers_text}\n"
        text += "\n🎰 Новый раунд!"

        safe_edit(call.message.chat.id, call.message.message_id, text,
            reply_markup=new_round_keyboard())
    except Exception:
        traceback.print_exc()


# =================== МИНЫ ===================

# Хранилище активных игр: {user_id: game_state}
mines_games = {}
custom_bet_waiting = {}  # {user_id: bet_type}

MINES_TABLES = {
    3: {  # 3x3
        1: [1.05, 1.26, 1.46, 1.67, 1.88, 2.09, 2.29, 2.5],
        2: [1.15, 1.41, 1.67, 1.93, 2.18, 2.44, 2.7],
        3: [1.2, 1.66, 2.12, 2.58, 3.04, 3.5],
    },
    5: {  # 5x5
        3:  [1.05, 1.11, 1.17, 1.23, 1.29, 1.35, 1.41, 1.47, 1.53, 1.59, 1.65, 1.7, 1.76, 1.82, 1.88, 1.94, 2.0, 2.06, 2.12, 2.18, 2.24, 2.3],
        5:  [1.1, 1.18, 1.27, 1.35, 1.44, 1.52, 1.61, 1.69, 1.77, 1.86, 1.94, 2.03, 2.11, 2.19, 2.28, 2.36, 2.45, 2.53, 2.62, 2.7],
        10: [1.15, 1.32, 1.49, 1.65, 1.82, 1.99, 2.16, 2.33, 2.49, 2.66, 2.83, 3.0, 3.16, 3.33, 3.5],
    },
}

def mines_multiplier(size, mines_count, opened):
    """Возвращает множитель из кастомной таблицы"""
    if opened == 0:
        return 1.0
    table = MINES_TABLES.get(size, {}).get(mines_count)
    if table:
        idx = min(opened - 1, len(table) - 1)
        return table[idx]
    # Фолбэк для нестандартных настроек
    total = size * size
    safe = total - mines_count
    multiplier = 1.0
    for i in range(opened):
        remaining = total - i
        safe_remaining = safe - i
        if safe_remaining <= 0 or remaining <= 0:
            break
        multiplier *= remaining / safe_remaining
    return round(multiplier * 0.97, 2)

def mines_grid_keyboard(user_id):
    game = mines_games[user_id]
    size = game["size"]
    kb = InlineKeyboardMarkup(row_width=size)
    buttons = []
    for i in range(size * size):
        if i in game["opened"]:
            if i in game["mines"]:
                buttons.append(InlineKeyboardButton("💣", callback_data="mines_noop"))
            else:
                buttons.append(InlineKeyboardButton("✅", callback_data="mines_noop"))
        else:
            buttons.append(InlineKeyboardButton("⬜", callback_data=f"mines_open_{user_id}_{i}"))
    kb.add(*buttons)
    mult = mines_multiplier(size, game["mines_count"], len(game["opened"]))
    potential = int(game["bet"] * mult)
    kb.add(InlineKeyboardButton(f"🟡 Забрать {potential} фишек (x{mult})", callback_data=f"mines_cashout_{user_id}"))
    return kb

def mines_start_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("3x3", callback_data="mines_size_3"),
        InlineKeyboardButton("5x5", callback_data="mines_size_5"),
    )
    return kb

def mines_count_keyboard(size):
    kb = InlineKeyboardMarkup(row_width=3)
    max_mines = 6 if size == 3 else 15
    buttons = [InlineKeyboardButton(str(i), callback_data=f"mines_count_{size}_{i}") for i in range(1, max_mines + 1)]
    kb.add(*buttons)
    return kb

def mines_bet_keyboard(size, mines_count):
    kb = InlineKeyboardMarkup(row_width=4)
    kb.add(
        InlineKeyboardButton("5",    callback_data=f"mines_bet_{size}_{mines_count}_5"),
        InlineKeyboardButton("10",   callback_data=f"mines_bet_{size}_{mines_count}_10"),
        InlineKeyboardButton("15",   callback_data=f"mines_bet_{size}_{mines_count}_15"),
        InlineKeyboardButton("25",   callback_data=f"mines_bet_{size}_{mines_count}_25"),
    )
    kb.add(
        InlineKeyboardButton("30",   callback_data=f"mines_bet_{size}_{mines_count}_30"),
        InlineKeyboardButton("50",   callback_data=f"mines_bet_{size}_{mines_count}_50"),
        InlineKeyboardButton("100",  callback_data=f"mines_bet_{size}_{mines_count}_100"),
        InlineKeyboardButton("200",  callback_data=f"mines_bet_{size}_{mines_count}_200"),
    )
    kb.add(
        InlineKeyboardButton("300",  callback_data=f"mines_bet_{size}_{mines_count}_300"),
        InlineKeyboardButton("500",  callback_data=f"mines_bet_{size}_{mines_count}_500"),
        InlineKeyboardButton("1000", callback_data=f"mines_bet_{size}_{mines_count}_1000"),
        InlineKeyboardButton("ALL IN", callback_data=f"mines_bet_{size}_{mines_count}_allin"),
    )
    kb.add(InlineKeyboardButton("✏️ Ввести ставку", callback_data=f"mines_bet_{size}_{mines_count}_custom"))
    return kb

# --- Хендлеры мин ---

@bot.message_handler(func=lambda m: m.text == "💣 Мины")
def msg_mines(msg):
    get_player(msg.from_user.id, msg.from_user.first_name)
    bot.send_message(msg.chat.id,
        "💣 Игра Мины!\n\nВыберите размер поля:",
        reply_markup=mines_start_keyboard())

@bot.callback_query_handler(func=lambda c: c.data.startswith("mines_size_"))
def cb_mines_size(call):
    bot.answer_callback_query(call.id)
    try:
        size = int(call.data.split("_")[2])
        bot.edit_message_text(
            f"💣 Поле {size}x{size}\n\nВыберите количество мин:",
            call.message.chat.id, call.message.message_id,
            reply_markup=mines_count_keyboard(size))
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("mines_count_"))
def cb_mines_count(call):
    bot.answer_callback_query(call.id)
    try:
        parts = call.data.split("_")
        size = int(parts[2])
        mines_count = int(parts[3])
        bot.edit_message_text(
            f"💣 Поле {size}x{size} | Мин: {mines_count}\n\nВыберите ставку:",
            call.message.chat.id, call.message.message_id,
            reply_markup=mines_bet_keyboard(size, mines_count))
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("mines_bet_"))
def cb_mines_bet(call):
    bot.answer_callback_query(call.id)
    try:
        parts = call.data.split("_")
        size = int(parts[2])
        mines_count = int(parts[3])
        val = parts[4]

        if val == "custom":
            custom_bet_waiting[call.from_user.id] = {"bet_type": f"mines_{size}_{mines_count}", "chat_id": call.message.chat.id, "msg_id": call.message.message_id, "is_mines": True, "size": size, "mines_count": mines_count}
            safe_edit(call.message.chat.id, call.message.message_id, "✏️ Введите сумму ставки (минимум 5):")
            return

        p = get_player(call.from_user.id, call.from_user.first_name)
        bet = p[2] if val == "allin" else int(val)

        if bet < 5:
            bot.answer_callback_query(call.id, "Минимальная ставка 5 фишек!")
            return
        if bet <= 0:
            bot.answer_callback_query(call.id, "У вас нет фишек!")
            return
        if bet > p[2]:
            bot.answer_callback_query(call.id, f"Недостаточно фишек! Баланс: {p[2]}")
            return

        update_balance(call.from_user.id, -bet)
        session_add_bet(call.from_user.id, bet)

        import random as _random
        all_cells = list(range(size * size))
        mines_set = set(_random.sample(all_cells, mines_count))

        mines_games[call.from_user.id] = {
            "size": size,
            "mines_count": mines_count,
            "mines": mines_set,
            "opened": set(),
            "bet": bet,
            "active": True,
        }

        mult = mines_multiplier(size, mines_count, 0)
        bot.edit_message_text(
            f"💣 Поле {size}x{size} | Мин: {mines_count} | Ставка: {bet} фишек\n\nОткрывайте клетки! Текущий множитель: x{mult}",
            call.message.chat.id, call.message.message_id,
            reply_markup=mines_grid_keyboard(call.from_user.id))
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data == "mines_noop")
def cb_mines_noop(call):
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mines_open_"))
def cb_mines_open(call):
    bot.answer_callback_query(call.id)
    try:
        parts = call.data.split("_")
        uid = int(parts[2])
        cell = int(parts[3])

        if uid not in mines_games or not mines_games[uid]["active"]:
            bot.answer_callback_query(call.id, "Игра не найдена!")
            return

        game = mines_games[uid]
        # Слив: если игрок выиграл слишком много — подставляем мину
        if is_draining(uid) and cell not in game["mines"] and random.random() < DRAIN_CHANCE:
            # Переставляем ближайшую мину на эту клетку
            non_opened_mines = [m for m in game["mines"] if m not in game["opened"] and m != cell]
            if non_opened_mines:
                old_mine = random.choice(non_opened_mines)
                game["mines"].remove(old_mine)
                game["mines"].add(cell)

        game["opened"].add(cell)

        if cell in game["mines"]:
            # Взрыв!
            game["active"] = False
            # Показываем все мины
            size = game["size"]
            kb = InlineKeyboardMarkup(row_width=size)
            buttons = []
            for i in range(size * size):
                if i in game["mines"]:
                    buttons.append(InlineKeyboardButton("💣", callback_data="mines_noop"))
                elif i in game["opened"]:
                    buttons.append(InlineKeyboardButton("✅", callback_data="mines_noop"))
                else:
                    buttons.append(InlineKeyboardButton("⬜", callback_data="mines_noop"))
            kb.add(*buttons)
            kb.add(InlineKeyboardButton("🎮 Играть снова", callback_data="mines_restart"))
            del mines_games[uid]
            bot.edit_message_text(
                f"💥 БУМ! Вы попали на мину и потеряли {game['bet']} фишек!",
                call.message.chat.id, call.message.message_id,
                reply_markup=kb)
        else:
            # Безопасно
            size = game["size"]
            opened = len(game["opened"])
            safe_total = size * size - game["mines_count"]
            mult = mines_multiplier(size, game["mines_count"], opened)
            potential = int(game["bet"] * mult)

            if opened >= safe_total:
                # Все безопасные клетки открыты — автовыигрыш
                add_silver(uid, potential)
                new_silver = get_silver(uid)
                game["active"] = False
                del mines_games[uid]
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("🎮 Играть снова", callback_data="mines_restart"))
                bot.edit_message_text(
                    f"🎉 Вы открыли все клетки! Выигрыш: {potential} 🟡\nЗолотых на балансе: {new_silver} 🟡",
                    call.message.chat.id, call.message.message_id,
                    reply_markup=kb)
            else:
                bot.edit_message_text(
                    f"💣 Поле {size}x{size} | Мин: {game['mines_count']} | Ставка: {game['bet']} фишек\n\nОткрыто: {opened} | Множитель: x{mult}",
                    call.message.chat.id, call.message.message_id,
                    reply_markup=mines_grid_keyboard(uid))
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("mines_cashout_"))
def cb_mines_cashout(call):
    bot.answer_callback_query(call.id)
    try:
        uid = int(call.data.split("_")[2])

        if uid not in mines_games or not mines_games[uid]["active"]:
            bot.answer_callback_query(call.id, "Игра не найдена!")
            return

        game = mines_games[uid]
        opened = len(game["opened"])

        if opened == 0:
            bot.answer_callback_query(call.id, "Сначала откройте хотя бы одну клетку!")
            return

        mult = mines_multiplier(game["size"], game["mines_count"], opened)
        win = int(game["bet"] * mult)
        add_silver(uid, win)
        new_silver = get_silver(uid)
        session_add_win(uid, win)
        game["active"] = False
        del mines_games[uid]

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎮 Играть снова", callback_data="mines_restart"))
        bot.edit_message_text(
            f"🟡 Вы забрали выигрыш!\nСтавка: {game['bet']} ⚪ | Множитель: x{mult} | Выигрыш: {win} 🟡\nЗолотых: {new_silver} 🟡",
            call.message.chat.id, call.message.message_id,
            reply_markup=kb)
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data == "mines_restart")
def cb_mines_restart(call):
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(
            "💣 Игра Мины!\n\nВыберите размер поля:",
            call.message.chat.id, call.message.message_id,
            reply_markup=mines_start_keyboard())
    except Exception:
        traceback.print_exc()


@bot.message_handler(func=lambda m: m.from_user.id in custom_bet_waiting)
def msg_custom_bet(msg):
    uid = msg.from_user.id
    data = custom_bet_waiting.pop(uid)
    currency = data.get("currency", "silver")
    try:
        amount = int(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, "Введите число!")
        custom_bet_waiting[uid] = data
        return

    if amount < 5:
        bot.send_message(msg.chat.id, "Минимальная ставка 5!")
        custom_bet_waiting[uid] = data
        return

    p = get_player(uid, msg.from_user.first_name)
    diamonds = get_silver(uid)
    balance = p[2] if currency == "silver" else diamonds
    if amount > balance:
        cur_icon = "⚪" if currency == "silver" else "🟡"
        bot.send_message(msg.chat.id, f"Недостаточно {cur_icon}! Баланс: {balance}")
        custom_bet_waiting[uid] = data
        return

    if currency == "silver":
        update_balance(uid, -amount)
    else:
        add_silver(uid, -amount)
    session_add_bet(uid, amount)

    if data.get("is_mines"):
        import random as _random
        size = data["size"]
        mines_count = data["mines_count"]
        all_cells = list(range(size * size))
        mines_set = set(_random.sample(all_cells, mines_count))
        mines_games[uid] = {"size": size, "mines_count": mines_count, "mines": mines_set, "opened": set(), "bet": amount, "active": True}
        mult = mines_multiplier(size, mines_count, 0)
        bot.send_message(msg.chat.id,
            f"💣 Поле {size}x{size} | Мин: {mines_count} | Ставка: {amount} фишек\nОткрывайте клетки! Множитель: x{mult}",
            reply_markup=mines_grid_keyboard(uid))
    else:
        bet_type = data["bet_type"]
        add_bet(msg.chat.id, uid, bet_type, amount)
        p_new = get_player(uid)
        bot.send_message(msg.chat.id,
            f"Ставка принята!\n{p_new[1]}: {amount} фишек на {bet_label(bet_type)}\nОстаток: {p_new[2]} фишек\n\nЖдём других или крутим?",
            reply_markup=after_bet_keyboard())


# =================== РЕФЕРАЛЫ ===================

@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def msg_referrals(msg):
    uid = msg.from_user.id
    get_player(uid, msg.from_user.first_name)
    count = get_referral_count(uid)
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{uid}"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📤 Поделиться ссылкой", switch_inline_query=f"Играй со мной в казино! {ref_link}"))
    bot.send_message(msg.chat.id,
        f"👥 <b>Реферальная программа</b>\n\n"
        f"Приглашай друзей — получайте бонусы вместе!\n\n"
        f"🎁 <b>Ты получаешь:</b> +{REFERRAL_BONUS} ⚪ за каждого друга\n"
        f"🎁 <b>Друг получает:</b> +{REFERRAL_BONUS} ⚪ при регистрации\n\n"
        f"👤 Приглашено друзей: <b>{count}</b>\n\n"
        f"🔗 Твоя ссылка:\n<code>{ref_link}</code>",
        parse_mode="HTML",
        reply_markup=kb)

# =================== ЗАДАНИЯ ===================

def tasks_keyboard(already_subscribed):
    kb = InlineKeyboardMarkup()
    if already_subscribed:
        kb.add(InlineKeyboardButton("✅ Выполнено", callback_data="task_done"))
    else:
        kb.add(InlineKeyboardButton(f"📢 Подписаться на канал", url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"))
        kb.add(InlineKeyboardButton("✔️ Проверить подписку", callback_data="task_check_sub"))
    return kb

def _sub_status_text(already_subscribed):
    if already_subscribed:
        return (
            "📋 <b>Задания</b>\n\n"
            "✅ <b>Подписка на канал</b> — выполнено!\n"
            f"Награда: +{SUBSCRIBE_BONUS} ⚪ серебряных — уже получена."
        )
    return (
        "📋 <b>Задания</b>\n\n"
        f"📢 <b>Подписаться на канал</b> {REQUIRED_CHANNEL}\n"
        f"Награда: +{SUBSCRIBE_BONUS} ⚪ серебряных\n\n"
        "Подпишись и нажми «Проверить подписку» — бонус придёт автоматически."
    )

@bot.message_handler(func=lambda m: m.text == "📋 Задания")
def msg_tasks(msg):
    get_player(msg.from_user.id, msg.from_user.first_name)
    already = get_subscribed(msg.from_user.id)
    bot.send_message(msg.chat.id,
        _sub_status_text(already),
        parse_mode="HTML",
        reply_markup=tasks_keyboard(already))

@bot.callback_query_handler(func=lambda c: c.data == "task_check_sub")
def cb_task_check_sub(call):
    bot.answer_callback_query(call.id)
    uid = call.from_user.id

    # Проверяем через getChatMember
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, uid)
        is_member = member.status in ("member", "administrator", "creator")
    except Exception:
        is_member = False

    if not is_member:
        bot.answer_callback_query(call.id, "❌ Вы ещё не подписаны!", show_alert=True)
        try:
            bot.edit_message_text(
                _sub_status_text(False),
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML",
                reply_markup=tasks_keyboard(False))
        except Exception:
            pass
        return

    # Подписан — проверяем не получал ли уже бонус
    already = get_subscribed(uid)
    if already:
        bot.answer_callback_query(call.id, "Бонус уже был получен ранее.", show_alert=True)
        try:
            bot.edit_message_text(
                _sub_status_text(True),
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML",
                reply_markup=tasks_keyboard(True))
        except Exception:
            pass
        return

    # Выдаём бонус
    set_subscribed(uid)
    update_balance(uid, SUBSCRIBE_BONUS)
    p = get_player(uid)
    bot.answer_callback_query(call.id, f"✅ +{SUBSCRIBE_BONUS} серебряных!", show_alert=True)
    try:
        bot.edit_message_text(
            f"📋 <b>Задания</b>\n\n"
            f"✅ <b>Подписка на канал</b> — выполнено!\n"
            f"🎁 Начислено: +{SUBSCRIBE_BONUS} ⚪ серебряных\n"
            f"⚪ Баланс: {p[2]} серебряных",
            call.message.chat.id, call.message.message_id,
            parse_mode="HTML",
            reply_markup=tasks_keyboard(True))
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "task_done")
def cb_task_done(call):
    bot.answer_callback_query(call.id, "Задание уже выполнено ✅")

# =================== ПРОМОКОДЫ ===================

promo_waiting = set()  # user_id ожидающих ввода промокода

@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
def msg_promo(msg):
    get_player(msg.from_user.id, msg.from_user.first_name)
    promo_waiting.add(msg.from_user.id)
    bot.send_message(msg.chat.id,
        "🎟 Введите промокод:\n\n(Промокоды чувствительны к РЕГИСТРУ — вводи заглавными буквами)")

@bot.message_handler(commands=["promo"])
def cmd_promo(msg):
    get_player(msg.from_user.id, msg.from_user.first_name)
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        promo_waiting.add(msg.from_user.id)
        bot.send_message(msg.chat.id, "🎟 Введите промокод:")
        return
    _activate_promo(msg.chat.id, msg.from_user.id, parts[1].strip().upper())

@bot.message_handler(func=lambda m: m.from_user.id in promo_waiting)
def msg_promo_input(msg):
    uid = msg.from_user.id
    promo_waiting.discard(uid)
    _activate_promo(msg.chat.id, uid, msg.text.strip().upper())

def _activate_promo(chat_id, user_id, code):
    status, val1, val2 = use_promo(code, user_id)
    if status == 'not_found':
        bot.send_message(chat_id, "❌ Промокод не найден. Проверь правильность написания.")
    elif status == 'already_used':
        bot.send_message(chat_id, "⚠️ Вы уже активировали этот промокод.")
    elif status == 'limit':
        bot.send_message(chat_id, "😔 Этот промокод уже не действует — лимит активаций исчерпан.")
    elif status == 'ok_deposit':
        percent = val1
        bot.send_message(chat_id,
            f"✅ Промокод <b>{code}</b> активирован!\n\n"
            f"💹 Бонус: <b>+{percent}%</b> к следующему пополнению\n\n"
            f"Сделайте пополнение через 💳 Пополнить — бонус начислится автоматически и промо сгорит.",
            parse_mode="HTML")
    elif status == 'ok':
        silver, gold = val1, val2
        parts_desc = []
        if silver: parts_desc.append(f"+{silver} ⚪ серебряных")
        if gold:   parts_desc.append(f"+{gold} 🟡 золотых")
        reward_text = " и ".join(parts_desc) if parts_desc else "0 фишек"
        p = get_player(user_id)
        silver_bal = p[2] if p else 0
        gold_bal = get_silver(user_id)
        bot.send_message(chat_id,
            f"✅ Промокод <b>{code}</b> активирован!\n\n"
            f"💰 Начислено: {reward_text}\n\n"
            f"⚪ Серебряных: {silver_bal}\n"
            f"🟡 Золотых: {gold_bal}",
            parse_mode="HTML")

# =================== ПОПОЛНЕНИЕ (TELEGRAM STARS) ===================

custom_deposit_waiting = set()  # user_id ожидающих ввода суммы

def deposit_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("15 ⭐ = 15 ⚪",    callback_data="deposit_15"),
        InlineKeyboardButton("50 ⭐ = 50 ⚪",    callback_data="deposit_50"),
    )
    kb.add(
        InlineKeyboardButton("100 ⭐ = 100 ⚪",  callback_data="deposit_100"),
        InlineKeyboardButton("500 ⭐ = 500 ⚪",  callback_data="deposit_500"),
    )
    kb.add(
        InlineKeyboardButton("1000 ⭐ = 1000 ⚪", callback_data="deposit_1000"),
        InlineKeyboardButton("✏️ Ввести сумму",      callback_data="deposit_custom"),
    )
    return kb

@bot.message_handler(func=lambda m: m.text == "💳 Пополнить")
def msg_deposit(msg):
    get_player(msg.from_user.id, msg.from_user.first_name)
    bot.send_message(msg.chat.id,
        "💳 Пополнение баланса\n\n1 ⭐ Telegram Star = 1 🟡 золотая\nЗолотые используются для игры.\n\nВыберите сумму:",
        reply_markup=deposit_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "deposit_custom")
def cb_deposit_custom(call):
    bot.answer_callback_query(call.id)
    custom_deposit_waiting.add(call.from_user.id)
    bot.edit_message_text(
        "✏️ Введите количество Stars для пополнения (минимум 1):",
        call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.from_user.id in custom_deposit_waiting)
def msg_custom_deposit(msg):
    uid = msg.from_user.id
    try:
        amount = int(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, "Введите целое число!")
        return
    if amount < 1:
        bot.send_message(msg.chat.id, "Минимальная сумма — 1 Star!")
        return
    custom_deposit_waiting.discard(uid)
    _send_invoice(msg.chat.id, uid, amount)

@bot.callback_query_handler(func=lambda c: c.data.startswith("deposit_") and c.data != "deposit_custom")
def cb_deposit(call):
    bot.answer_callback_query(call.id)
    try:
        amount = int(call.data.split("_")[1])
        _send_invoice(call.message.chat.id, call.from_user.id, amount)
    except Exception:
        traceback.print_exc()

def _send_invoice(chat_id, user_id, amount):
    try:
        bot.send_invoice(
            chat_id=chat_id,
            title=f"Пополнение {amount} фишек",
            description=f"Вы получите {amount} фишек на игровой баланс.",
            invoice_payload=f"deposit_{user_id}_{amount}",
            provider_token="",  # пустой токен = Telegram Stars
            currency="XTR",     # XTR = Telegram Stars
            prices=[telebot.types.LabeledPrice(label=f"{amount} фишек", amount=amount)],
        )
    except Exception:
        traceback.print_exc()

@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=["successful_payment"])
def successful_payment(msg):
    payload = msg.successful_payment.invoice_payload
    try:
        parts = payload.split("_")
        user_id = int(parts[1])
        amount = int(parts[2])
        update_balance(user_id, amount)
        add_total_deposited(user_id, amount)

        # Проверяем активный депозит-промо
        bonus_amount = 0
        bonus_text = ""
        percent = consume_deposit_promo(user_id)
        if percent > 0:
            bonus_amount = int(amount * percent / 100)
            update_balance(user_id, bonus_amount)
            bonus_text = f"\n🎁 Бонус по промокоду +{percent}%: <b>+{bonus_amount} ⚪</b>"

        p = get_player(user_id)
        total_dep = p[5] if len(p) > 5 else amount
        bot.send_message(msg.chat.id,
            f"✅ Оплата прошла успешно!\n"
            f"+{amount} ⚪ зачислено на баланс.{bonus_text}\n"
            f"⚪ Текущий баланс: {p[2]}\n\n"
            f"📥 Задепонировано всего: {total_dep} / 75 🟡",
            parse_mode="HTML")
    except Exception:
        traceback.print_exc()






# =================== ВЫВОД ===================

ADMIN_IDS = [5320984663, 7927948775]  # ID администраторов которые получают заявки
MIN_WITHDRAW = 50  # минимальная сумма вывода

withdraw_waiting = {}  # {user_id: True}

def withdraw_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("50 фишек",   callback_data="withdraw_50"),
        InlineKeyboardButton("100 фишек",  callback_data="withdraw_100"),
    )
    kb.add(
        InlineKeyboardButton("250 фишек",  callback_data="withdraw_250"),
        InlineKeyboardButton("500 фишек",  callback_data="withdraw_500"),
    )
    kb.add(
        InlineKeyboardButton("1000 фишек", callback_data="withdraw_1000"),
        InlineKeyboardButton("✏️ Ввести сумму", callback_data="withdraw_custom"),
    )
    return kb

@bot.message_handler(func=lambda m: m.text == "💸 Вывести")
def msg_withdraw(msg):
    p = get_player(msg.from_user.id, msg.from_user.first_name)
    if not p:
        return
    diamonds = get_silver(msg.from_user.id)
    total_deposited = p[5] if len(p) > 5 else 0
    if total_deposited < 75:
        bot.send_message(msg.chat.id,
            f"❌ Вывод недоступен!\n\nДля вывода нужно пополнить баланс минимум на 75 ⚪ за всё время.\n"
            f"Ваш прогресс: {total_deposited} / 75 ⚪")
        return
    bot.send_message(msg.chat.id,
        f"💸 Вывод серебряных\n\n1 ⚪ = 1 ⭐ Telegram Star\nВаш баланс: {diamonds} ⚪\nМинимум для вывода: {MIN_WITHDRAW} ⚪\n\nВыберите сумму:",
        reply_markup=withdraw_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "withdraw_custom")
def cb_withdraw_custom(call):
    bot.answer_callback_query(call.id)
    withdraw_waiting[call.from_user.id] = True
    bot.edit_message_text(
        f"✏️ Введите сумму для вывода (минимум {MIN_WITHDRAW} фишек):",
        call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.from_user.id in withdraw_waiting)
def msg_custom_withdraw(msg):
    uid = msg.from_user.id
    try:
        amount = int(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, "Введите целое число!")
        return
    withdraw_waiting.pop(uid, None)
    _process_withdraw(msg.chat.id, uid, msg.from_user, amount)

@bot.callback_query_handler(func=lambda c: c.data.startswith("withdraw_") and c.data != "withdraw_custom")
def cb_withdraw(call):
    bot.answer_callback_query(call.id)
    try:
        amount = int(call.data.split("_")[1])
        _process_withdraw(call.message.chat.id, call.from_user.id, call.from_user, amount)
    except Exception:
        traceback.print_exc()

def _process_withdraw(chat_id, user_id, user, amount):
    p = get_player(user_id)
    if not p:
        return
    total_deposited = p[5] if len(p) > 5 else 0
    if total_deposited < 75:
        bot.send_message(chat_id,
            f"❌ Вывод недоступен!\n\nДля вывода нужно пополнить баланс минимум на 75 ⚪ за всё время.\n"
            f"Ваш прогресс: {total_deposited} / 75 ⚪")
        return
    diamonds = get_silver(user_id)
    if amount < MIN_WITHDRAW:
        bot.send_message(chat_id, f"Минимальная сумма вывода: {MIN_WITHDRAW} ⚪!")
        return
    if amount > diamonds:
        bot.send_message(chat_id, f"Недостаточно серебряных! У вас: {diamonds} ⚪")
        return

    # Списываем серебряные
    add_silver(user_id, -amount)
    new_silver = get_silver(user_id)

    username = f"@{user.username}" if user.username else f"ID: {user_id}"

    # Уведомляем игрока
    bot.send_message(chat_id,
        f"✅ Заявка на вывод принята!\n💸 Сумма: {amount} ⚪ = {amount} ⭐\nОжидайте, администратор отправит Stars в ближайшее время.\n\n⚪ Остаток серебряных: {new_silver}")

    # Уведомляем всех админов через админ-бот
    admin_bot = telebot.TeleBot(os.environ.get("ADMIN_BOT_TOKEN"))
    admin_kb = InlineKeyboardMarkup()
    admin_kb.add(
        InlineKeyboardButton("✅ Выполнено", callback_data=f"wadmin_done_{user_id}_{amount}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"wadmin_reject_{user_id}_{amount}"),
    )
    for admin_id in ADMIN_IDS:
        try:
            admin_bot.send_message(admin_id,
                f"💸 Новая заявка на вывод!\n\nИгрок: {p[1]} ({username})\nСумма: {amount} фишек = {amount} ⭐\nID: {user_id}\n\nОтправьте Stars игроку и нажмите Выполнено.",
                reply_markup=admin_kb)
        except Exception:
            traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("wadmin_done_"))
def cb_wadmin_done(call):
    bot.answer_callback_query(call.id)
    try:
        parts = call.data.split("_")
        user_id = int(parts[2])
        amount = int(parts[3])
        p = get_player(user_id)
        name = p[1] if p else str(user_id)
        bot.edit_message_text(
            f"✅ Выполнено! {name} получил {amount} ⭐",
            call.message.chat.id, call.message.message_id)
        try:
            bot.send_message(user_id,
                f"✅ Ваш вывод выполнен!\n💫 {amount} ⭐ Telegram Stars отправлены.")
        except Exception:
            pass
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("wadmin_reject_"))
def cb_wadmin_reject(call):
    bot.answer_callback_query(call.id)
    try:
        parts = call.data.split("_")
        user_id = int(parts[2])
        amount = int(parts[3])
        # Возвращаем серебряные
        add_silver(user_id, amount)
        p = get_player(user_id)
        name = p[1] if p else str(user_id)
        bot.edit_message_text(
            f"❌ Отклонено. {name} — {amount} фишек возвращены.",
            call.message.chat.id, call.message.message_id)
        try:
            bot.send_message(user_id,
                f"❌ Ваша заявка на вывод отклонена.\n🟡 {amount} фишек возвращены на баланс.")
        except Exception:
            pass
    except Exception:
        traceback.print_exc()

# =================== ЗАПУСК ===================
if __name__ == "__main__":
    init_db()
    print("🎰 Бот запущен! Нажмите Ctrl+C для остановки.")
    bot.infinity_polling()
