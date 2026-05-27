#!/bin/bash

echo "=== Исправляю gamification.py ==="
cat > /opt/bot/gamification.py << 'PYEOF'
import random
from datetime import datetime
from config import LEVELS, EXP_SOURCES, ACHIEVEMENTS, WEEKLY_PRIZES
from database import get_db

def get_level_by_exp(exp: int) -> int:
    lvl = 1
    for level in sorted(LEVELS.keys()):
        if exp >= LEVELS[level]["exp_required"]:
            lvl = level
    return lvl

async def add_exp(user_id: int, source: str):
    exp_data = EXP_SOURCES.get(source, {})
    amount = exp_data.get("exp", 0)
    if not amount:
        return None
    db = await get_db()
    cursor = await db.execute('SELECT current_exp, total_exp, current_level FROM user_levels WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    cur, total, lvl = row if row else (0, 0, 1)
    if not row:
        await db.execute('INSERT INTO user_levels (user_id) VALUES (?)', (user_id,))
    new_exp = cur + amount
    new_total = total + amount
    new_lvl = get_level_by_exp(new_exp)
    await db.execute('UPDATE user_levels SET current_exp = ?, total_exp = ?, current_level = ? WHERE user_id = ?',
                    (new_exp, new_total, new_lvl, user_id))
    await db.execute('INSERT INTO exp_history (user_id, amount, source, description, timestamp) VALUES (?, ?, ?, ?, ?)',
                    (user_id, amount, source, exp_data["desc"], datetime.now().isoformat()))
    await db.execute('UPDATE users SET reputation_points = COALESCE(reputation_points, 0) + ? WHERE user_id = ?',
                    (amount // 2, user_id))
    await db.commit()
    return {"leveled_up": new_lvl > lvl, "old": lvl, "new": new_lvl} if new_lvl > lvl else None

async def check_achievements(user_id: int):
    db = await get_db()
    cursor = await db.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
    refs = (await cursor.fetchone())[0]
    cursor = await db.execute('SELECT join_date FROM users WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    months = (datetime.now() - datetime.fromisoformat(row[0])).days // 30 if row and row[0] else 0
    checks = {"first_ref": refs >= 1, "ref_5": refs >= 5, "ref_10": refs >= 10, "ref_25": refs >= 25, "sub_3_months": months >= 3}
    new_ach = []
    for key, ok in checks.items():
        if not ok:
            continue
        cursor = await db.execute('SELECT id FROM achievements WHERE user_id = ? AND achievement_key = ?', (user_id, key))
        if await cursor.fetchone():
            continue
        await db.execute('INSERT INTO achievements (user_id, achievement_key, unlocked_at) VALUES (?, ?, ?)',
                       (user_id, key, datetime.now().isoformat()))
        reward = ACHIEVEMENTS[key].get("reward_days", 0)
        if reward:
            await db.execute('UPDATE users SET referral_balance_days = COALESCE(referral_balance_days, 0) + ? WHERE user_id = ?',
                           (reward, user_id))
        new_ach.append(key)
    await db.commit()
    return new_ach

async def run_lottery(bot) -> str:
    week = int(datetime.now().strftime("%Y%W"))
    db = await get_db()
    cursor = await db.execute('SELECT user_id, COALESCE(lottery_tickets, 0) FROM users WHERE COALESCE(lottery_tickets, 0) > 0')
    participants = await cursor.fetchall()
    if not participants:
        return "Нет участников"
    drum = [uid for uid, tickets in participants for _ in range(tickets)]
    random.shuffle(drum)
    winners = list(dict.fromkeys(drum))[:3]
    text = f"🎰 Розыгрыш недели #{week}\n\n"
    for i, wid in enumerate(winners):
        prize = WEEKLY_PRIZES[i + 1]["days"]
        await db.execute('INSERT INTO weekly_lottery (user_id, week_number, won, prize_days) VALUES (?, ?, 1, ?)', (wid, week, prize))
        await db.execute('UPDATE users SET referral_balance_days = COALESCE(referral_balance_days, 0) + ?, lottery_tickets = 0 WHERE user_id = ?', (prize, wid))
        cursor = await db.execute('SELECT username FROM users WHERE user_id = ?', (wid,))
        row = await cursor.fetchone()
        un = row[0] if row and row[0] else f"ID:{wid}"
        text += f"{['🥇','🥈','🥉'][i]} @{un} — +{prize} дн.\n"
        await add_exp(wid, "lottery_win")
    await db.execute("UPDATE users SET lottery_tickets = 0 WHERE lottery_tickets > 0")
    await db.commit()
    for wid in winners:
        try:
            await bot.send_message(wid, f"🎉 Вы выиграли {prize} дней подписки!")
        except:
            pass
    return text
PYEOF

echo "=== Исправляю tasks.py ==="
cat > /opt/bot/tasks.py << 'PYEOF'
import random
from datetime import datetime, timedelta
from config import TASK_TYPES
from database import get_db

def get_daily_tasks() -> list:
    pool = [t for t in TASK_TYPES if TASK_TYPES[t].get("category", "") != "streak"]
    selected = random.sample(pool, min(3, len(pool)))
    if "daily_login" not in selected:
        selected.append("daily_login")
    return selected[:4]

async def assign_tasks(user_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    db = await get_db()
    cursor = await db.execute('SELECT COUNT(*) FROM user_daily_tasks WHERE user_id = ? AND assigned_date = ?', (user_id, today))
    if (await cursor.fetchone())[0] > 0:
        return
    for task_key in get_daily_tasks():
        await db.execute('INSERT OR IGNORE INTO user_daily_tasks (user_id, task_key, target, assigned_date) VALUES (?, ?, ?, ?)',
                       (user_id, task_key, TASK_TYPES[task_key]["target"], today))
    await db.commit()

async def update_task_progress(user_id: int, task_key: str, inc: int = 1):
    today = datetime.now().strftime("%Y-%m-%d")
    db = await get_db()
    cursor = await db.execute('SELECT id, progress, target, completed FROM user_daily_tasks WHERE user_id = ? AND task_key = ? AND assigned_date = ?',
                             (user_id, task_key, today))
    task = await cursor.fetchone()
    if not task or task[3]:
        return None
    tid, prog, target, _ = task
    new_prog = prog + inc
    if new_prog >= target:
        t = TASK_TYPES.get(task_key, {})
        await db.execute('UPDATE user_daily_tasks SET progress = ?, completed = 1 WHERE id = ?', (target, tid))
        await db.execute('UPDATE users SET lottery_tickets = COALESCE(lottery_tickets, 0) + ?, referral_balance_days = COALESCE(referral_balance_days, 0) + ?, reputation_points = COALESCE(reputation_points, 0) + ? WHERE user_id = ?',
                       (t.get("reward_tickets", 0), t.get("reward_days", 0), t.get("reward_days", 0) * 5, user_id))
        await db.commit()
        return {"completed": True, "task": t}
    else:
        await db.execute('UPDATE user_daily_tasks SET progress = ? WHERE id = ?', (new_prog, tid))
        await db.commit()

async def update_streak(user_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    db = await get_db()
    await db.execute('INSERT OR IGNORE INTO daily_activity (user_id, activity_date) VALUES (?, ?)', (user_id, today))
    cursor = await db.execute('SELECT COALESCE(current_streak, 0), COALESCE(longest_streak, 0), last_activity_date FROM users WHERE user_id = ?', (user_id,))
    cur, longest, last = (await cursor.fetchone()) or (0, 0, None)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    cur = cur + 1 if last == yesterday else 1
    await db.execute('UPDATE users SET current_streak = ?, longest_streak = MAX(COALESCE(longest_streak, 0), ?), last_activity_date = ? WHERE user_id = ?',
                    (cur, cur, today, user_id))
    await db.commit()
    for days in [3, 7]:
        if cur == days:
            await update_task_progress(user_id, f"streak_{days}", days)
    return cur
PYEOF

echo "=== Исправляю handlers_admin.py ==="
cat > /opt/bot/handlers_admin.py << 'PYEOF'
import asyncio
from datetime import datetime
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import ADMIN_ID
from database import get_db
from keyboards import admin_kb
from gamification import run_lottery

router = Router()

class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirm = State()

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🔐 Админ-панель", reply_markup=admin_kb())

@router.callback_query(lambda c: c.data == "adm_stats")
async def adm_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    db = await get_db()
    cursor = await db.execute('SELECT COUNT(*) FROM users')
    total = (await cursor.fetchone())[0]
    cursor = await db.execute('SELECT COUNT(*) FROM users WHERE expire_date > ?', (datetime.now().isoformat(),))
    active = (await cursor.fetchone())[0]
    cursor = await db.execute('SELECT COALESCE(SUM(total_paid), 0) FROM users')
    rev = (await cursor.fetchone())[0]
    month = datetime.now().replace(day=1).isoformat()
    cursor = await db.execute('SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE timestamp > ?', (month,))
    mp, mr = await cursor.fetchone()
    text = f"📊 Статистика\n\n👥 Всего: {total}\n✅ Активных: {active}\n💰 Выручка: {rev:.2f} USDT\n📅 За месяц: {mp} пл. / {mr:.2f} USDT"
    await callback.message.edit_text(text, reply_markup=admin_kb())

@router.callback_query(lambda c: c.data == "adm_lottery")
async def adm_lottery(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    text = await run_lottery(callback.bot)
    await callback.message.edit_text(text, reply_markup=admin_kb())

@router.callback_query(lambda c: c.data == "adm_broadcast")
async def adm_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.edit_text("📢 Отправь сообщение для рассылки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm_back")]
    ]))
    await state.set_state(BroadcastStates.waiting_for_message)

@router.message(BroadcastStates.waiting_for_message)
async def broadcast_msg(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить всем", callback_data="broadcast_send")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm_back")],
    ])
    await message.answer("Подтверди:", reply_markup=kb)
    await state.set_state(BroadcastStates.confirm)

@router.callback_query(lambda c: c.data == "broadcast_send", BroadcastStates.confirm)
async def broadcast_send(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    msg_id = data.get("msg_id")
    chat_id = data.get("chat_id")
    db = await get_db()
    cursor = await db.execute('SELECT user_id FROM users')
    users = await cursor.fetchall()
    ok = fail = 0
    for (uid,) in users:
        try:
            await callback.bot.copy_message(chat_id=uid, from_chat_id=chat_id, message_id=msg_id)
            ok += 1
        except:
            fail += 1
        await asyncio.sleep(0.05)
    await callback.message.edit_text(f"📢 Готово\n✅ {ok} | ❌ {fail}", reply_markup=admin_kb())
    await state.clear()

@router.callback_query(lambda c: c.data == "adm_back")
async def adm_back(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await callback.message.edit_text("🔐 Админ-панель", reply_markup=admin_kb())

@router.callback_query(lambda c: c.data == "adm_blacklist")
async def adm_blacklist(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    db = await get_db()
    cursor = await db.execute('SELECT user_id, reason, banned_at, unban_count FROM blacklist ORDER BY banned_at DESC LIMIT 10')
    rows = await cursor.fetchall()
    if not rows:
        await callback.message.edit_text("Чёрный список пуст.", reply_markup=admin_kb())
        return
    text = "⛔ *Чёрный список*\n\n" + "\n".join(f"ID:{uid} | {r} | {b[:10]} | разблок: {u}" for uid, r, b, u in rows)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=admin_kb())
PYEOF

echo "=== Исправляю cron.py ==="
cat > /opt/bot/cron.py << 'PYEOF'
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot
from config import BOT_TOKEN
from database import get_db

async def check_expired():
    bot = Bot(token=BOT_TOKEN)
    db = await get_db()
    cursor = await db.execute('SELECT user_id FROM users WHERE expire_date < ? AND expire_date IS NOT NULL', (datetime.now().isoformat(),))
    expired = await cursor.fetchall()
    for (uid,) in expired:
        try:
            await bot.send_message(uid, "⏰ Подписка истекла. Продли: /start")
        except:
            pass
    cursor = await db.execute("SELECT user_id FROM users WHERE expire_date < ? AND expire_date > ? AND total_paid <= 3",
                             (datetime.now() + timedelta(hours=12), datetime.now().isoformat()))
    trial_ending = await cursor.fetchall()
    for (uid,) in trial_ending:
        try:
            await bot.send_message(uid, "⏰ Пробный период заканчивается через 12 ч. Продли: /start")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(check_expired())
PYEOF

systemctl restart tradeall-bot
echo "=== Готово. Бот перезапущен. ==="
