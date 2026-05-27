#!/bin/bash
cat > /opt/bot/handlers_user.py << 'PYEOF'
import random
import aiosqlite
from datetime import datetime, timedelta
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import *
from database import get_db
from keyboards import main_kb, payment_methods_kb
from payment import check_ton_transaction, check_trc20_transaction
from referral import get_or_create_ref_code, process_referral, update_lottery_tickets
from gamification import add_exp, check_achievements
from tasks import assign_tasks, update_streak, update_task_progress

router = Router()

async def create_invite_link(bot: Bot, user_id: int) -> str:
    db = await get_db()
    cursor = await db.execute('SELECT link FROM invite_links WHERE user_id = ? AND used_by IS NULL', (user_id,))
    existing = await cursor.fetchone()
    if existing:
        return existing[0]
    try:
        invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1, name=f"user_{user_id}")
        await db.execute('INSERT INTO invite_links (user_id, link, created_at) VALUES (?, ?, ?)',
                       (user_id, invite.invite_link, datetime.now().isoformat()))
        await db.commit()
        return invite.invite_link
    except:
        return None

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    ref_code = args[1] if len(args) > 1 else None

    db = await get_db()
    cursor = await db.execute('SELECT referred_by FROM users WHERE user_id = ?', (user_id,))
    exists = await cursor.fetchone()
    if ref_code and not exists:
        cursor = await db.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref_code,))
        ref = await cursor.fetchone()
        if ref and ref[0] != user_id:
            await db.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (ref[0], user_id))
            await db.commit()
            await process_referral(ref[0], user_id)
            await add_exp(ref[0], "referral_register")
            await update_lottery_tickets(ref[0])
            try:
                await message.bot.send_message(ref[0], f"🎉 Новый реферал! +{REFERRAL_BONUS_TRIAL} дн.")
            except:
                pass

    await assign_tasks(user_id)
    await update_streak(user_id)
    await add_exp(user_id, "daily_login")

    await message.answer(
        "🎯 *TradeAll | Закрытый клуб*\n\n"
        "💎 Подписка: 25 USDT/мес\n"
        "🔑 Пробник: 3 USDT на 3 дня\n\n"
        "📋 /tasks — задания\n"
        "👥 /referral — партнёрка\n"
        "🏆 /level — звания\n"
        "📊 /profile — профиль\n"
        "🎰 /lottery — розыгрыш\n"
        "📄 /terms — условия\n"
        "📋 /rules — правила\n"
        "📞 /support — поддержка",
        parse_mode="Markdown",
        reply_markup=main_kb()
    )

@router.callback_query(lambda c: c.data == "buy_sub")
async def buy_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    unique = round(PRICE_USDT + random.randint(1, 99) / 100, 2)
    db = await get_db()
    await db.execute('INSERT INTO users (user_id, unique_amount) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET unique_amount = ?',
                    (user_id, unique, unique))
    await db.commit()
    await callback.message.edit_text(
        f"💎 *Подписка — {PRICE_USDT} USDT/мес*\n\n"
        f"Отправьте *ровно {unique} USDT*:\n\n"
        f"🔹 TON: `{TON_WALLET}`\n"
        f"🔹 TRC20: `{TRC20_WALLET}`\n\n"
        f"📄 /terms",
        parse_mode="Markdown",
        reply_markup=payment_methods_kb("check_sub")
    )

@router.callback_query(lambda c: c.data == "buy_trial")
async def buy_trial(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT trial_used FROM users WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    if row and row[0]:
        await callback.answer("Ты уже брал пробный период!", show_alert=True)
        return
    unique = round(TRIAL_PRICE + random.randint(1, 99) / 100, 2)
    await db.execute('INSERT INTO users (user_id, unique_amount) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET unique_amount = ?',
                    (user_id, unique, unique))
    await db.commit()
    await callback.message.edit_text(
        f"🔑 *Пробный период — {TRIAL_PRICE} USDT на {TRIAL_DAYS} дня*\n\n"
        f"Отправьте *ровно {unique} USDT*:\n\n"
        f"🔹 TON: `{TON_WALLET}`\n"
        f"🔹 TRC20: `{TRC20_WALLET}`\n\n"
        f"📄 /terms",
        parse_mode="Markdown",
        reply_markup=payment_methods_kb("check_trial")
    )

async def process_payment(callback, network: str, is_trial: bool):
    user_id = callback.from_user.id
    wallet = TON_WALLET if network == "TON" else TRC20_WALLET
    price = TRIAL_PRICE if is_trial else PRICE_USDT
    days = TRIAL_DAYS if is_trial else 30

    db = await get_db()
    cursor = await db.execute('SELECT unique_amount FROM users WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    if not row or not row[0]:
        await callback.answer("Нажми кнопку оплаты сначала", show_alert=True)
        return

    amount = row[0]
    await callback.message.edit_text(f"🔍 Проверяю {network}...")

    result = await check_ton_transaction(amount, wallet) if network == "TON" else await check_trc20_transaction(amount, wallet)

    if result.get("found"):
        expire = datetime.now() + timedelta(days=days)
        await db.execute('UPDATE users SET expire_date = ?, total_paid = COALESCE(total_paid, 0) + ?, trial_used = 1 WHERE user_id = ?',
                       (expire.isoformat(), price, user_id))
        await db.execute('INSERT INTO payments (user_id, amount, network, tx_hash, timestamp) VALUES (?, ?, ?, ?, ?)',
                       (user_id, amount, network, result.get("tx_hash"), datetime.now().isoformat()))
        cursor = await db.execute('SELECT referred_by FROM users WHERE user_id = ?', (user_id,))
        ref = await cursor.fetchone()
        await db.commit()

        if ref and ref[0]:
            await process_referral(ref[0], user_id, is_trial)
            await update_lottery_tickets(ref[0])
        await add_exp(user_id, "renew_subscription")
        await check_achievements(user_id)

        link = await create_invite_link(callback.bot, user_id)
        await callback.message.edit_text(
            f"✅ Доступ открыт!\n📅 До: {expire.strftime('%d.%m.%Y')}\n\n🔗 {link}\n\n⚠️ Ссылка одноразовая!",
            reply_markup=main_kb()
        )
    else:
        await callback.message.edit_text("❌ Платёж не найден. Проверь сумму.", reply_markup=payment_methods_kb("check_trial" if is_trial else "check_sub"))

@router.callback_query(lambda c: c.data in ["check_sub_ton", "check_sub_trc20", "check_trial_ton", "check_trial_trc20"])
async def check_payment(callback: types.CallbackQuery):
    is_trial = "trial" in callback.data
    network = "TON" if "ton" in callback.data else "TRC20"
    await process_payment(callback, network, is_trial)

@router.callback_query(lambda c: c.data == "ref_menu")
async def ref_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("👥 /referral — партнёрский кабинет\n📊 /top — рейтинг\n🏆 /level — звания", reply_markup=main_kb())

@router.callback_query(lambda c: c.data == "back_main")
async def back_main(callback: types.CallbackQuery):
    await callback.message.edit_text("🎯 Главное меню", reply_markup=main_kb())

@router.callback_query(lambda c: c.data == "support")
async def cmd_support(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📞 *Поддержка TradeAll*\n\nПо всем вопросам: @TradeAll_Support\n\nОтвечаю в течение часа.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]])
    )

@router.message(Command("support"))
async def cmd_support_msg(message: types.Message):
    await message.answer("📞 *Поддержка TradeAll*\n\nПо всем вопросам: @TradeAll_Support", parse_mode="Markdown")

@router.message(Command("referral"))
async def cmd_referral(message: types.Message):
    user_id = message.from_user.id
    code = await get_or_create_ref_code(user_id)
    bot_name = (await message.bot.get_me()).username
    ref_link = f"https://t.me/{bot_name}?start={code}"
    db = await get_db()
    cursor = await db.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
    total = (await cursor.fetchone())[0]
    cursor = await db.execute('SELECT COUNT(*) FROM referrals r JOIN users u ON r.referred_id = u.user_id WHERE r.referrer_id = ? AND u.expire_date > ?',
                             (user_id, datetime.now().isoformat()))
    active = (await cursor.fetchone())[0]
    cursor = await db.execute('SELECT COALESCE(referral_balance_days, 0), COALESCE(lottery_tickets, 0) FROM users WHERE user_id = ?', (user_id,))
    bal, tickets = (await cursor.fetchone()) or (0, 0)
    await message.answer(
        f"👥 *Партнёрский кабинет*\n\n🔗 `{ref_link}`\n\n📊 Всего: {total} | Активных: {active}\n💎 Баланс: {bal} дн.\n🎫 Билеты: {tickets}\n\n"
        f"+{REFERRAL_BONUS_TRIAL} дн. за пробник друга\n+{REFERRAL_BONUS_DAYS} дн. за подписку друга\nДни продлевают твою подписку.",
        parse_mode="Markdown"
    )

@router.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT COALESCE(referral_balance_days, 0), COALESCE(lottery_tickets, 0), COALESCE(reputation_points, 0) FROM users WHERE user_id = ?', (user_id,))
    bal, tickets, rep = (await cursor.fetchone()) or (0, 0, 0)
    cursor = await db.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
    refs = (await cursor.fetchone())[0]
    cursor = await db.execute('SELECT COUNT(*) FROM achievements WHERE user_id = ?', (user_id,))
    ach = (await cursor.fetchone())[0]
    cursor = await db.execute('SELECT current_exp, current_level FROM user_levels WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    exp, lvl = row if row else (0, 1)
    await message.answer(
        f"👤 *Профиль*\n\n👥 Рефералов: {refs}\n🏆 Достижений: {ach}/{len(ACHIEVEMENTS)}\n"
        f"⭐ Уровень: {lvl}\n💎 Бонусов: {bal} дн.\n🎫 Билетов: {tickets}\n🌟 Репутация: {rep}",
        parse_mode="Markdown"
    )

@router.message(Command("level"))
async def cmd_level(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT current_exp, total_exp, current_level FROM user_levels WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    cur, total, lvl = row if row else (0, 0, 1)
    ld = LEVELS.get(lvl, LEVELS[max(LEVELS.keys())])
    await message.answer(f"{ld['emoji']} *Уровень {lvl}* — {ld['name']}\nОпыт: {cur} XP\nВсего: {total} XP", parse_mode="Markdown")

@router.message(Command("top"))
async def cmd_top(message: types.Message):
    db = await get_db()
    cursor = await db.execute('SELECT r.referrer_id, u.username, COUNT(*) as cnt FROM referrals r LEFT JOIN users u ON r.referrer_id = u.user_id GROUP BY r.referrer_id ORDER BY cnt DESC LIMIT 10')
    top = await cursor.fetchall()
    if not top:
        await message.answer("Рефералов пока нет.")
        return
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
    text = "🏆 *Топ рефереров*\n\n" + "\n".join(f"{medals[i]} @{un or f'ID:{uid}'} — {cnt}" for i, (uid, un, cnt) in enumerate(top))
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("lottery"))
async def cmd_lottery(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT COALESCE(lottery_tickets, 0) FROM users WHERE user_id = ?', (user_id,))
    tickets = (await cursor.fetchone())[0]
    days_to_sun = (6 - datetime.now().weekday()) % 7 or 7
    next_draw = (datetime.now() + timedelta(days=days_to_sun)).replace(hour=20, minute=0, second=0)
    await message.answer(f"🎰 *Розыгрыш*\n\n📅 {next_draw.strftime('%d.%m.%Y 20:00')}\n🎫 Билетов: {tickets}\n\nПризы: 30/14/7 дн.", parse_mode="Markdown")

@router.message(Command("achievements"))
async def cmd_achievements(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT achievement_key FROM achievements WHERE user_id = ?', (user_id,))
    unlocked = {r[0] for r in await cursor.fetchall()}
    text = "🏅 *Достижения*\n\n" + "\n".join(f"{v['emoji']} *{v['title']}* {'✅' if k in unlocked else '🔒'}" for k, v in ACHIEVEMENTS.items())
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    user_id = message.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    await assign_tasks(user_id)
    streak = await update_streak(user_id)
    db = await get_db()
    cursor = await db.execute('SELECT task_key, progress, target, completed, reward_claimed FROM user_daily_tasks WHERE user_id = ? AND assigned_date = ?', (user_id, today))
    tasks = await cursor.fetchall()
    cursor = await db.execute('SELECT COALESCE(lottery_tickets, 0) FROM users WHERE user_id = ?', (user_id,))
    tickets = (await cursor.fetchone())[0]
    text = f"📋 *Задания*\n🔥 Серия: {streak} дн. | 🎫 {tickets}\n\n"
    for tk, prog, target, done, claimed in tasks:
        t = TASK_TYPES.get(tk, {})
        status = "✅" if done and claimed else ("🎁" if done else f"{prog}/{target}")
        text += f"{t.get('icon','❓')} *{t.get('title',tk)}*: {status}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 Забрать награды", callback_data="claim_tasks")]])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

@router.callback_query(lambda c: c.data == "claim_tasks")
async def claim_tasks(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    db = await get_db()
    cursor = await db.execute('SELECT id, task_key FROM user_daily_tasks WHERE user_id = ? AND assigned_date = ? AND completed = 1 AND reward_claimed = 0', (user_id, today))
    unclaimed = await cursor.fetchall()
    tt = td = 0
    for tid, tk in unclaimed:
        t = TASK_TYPES.get(tk, {})
        tt += t.get("reward_tickets", 0)
        td += t.get("reward_days", 0)
        await db.execute('UPDATE user_daily_tasks SET reward_claimed = 1 WHERE id = ?', (tid,))
    if tt or td:
        await db.execute('UPDATE users SET lottery_tickets = COALESCE(lottery_tickets, 0) + ?, referral_balance_days = COALESCE(referral_balance_days, 0) + ? WHERE user_id = ?', (tt, td, user_id))
    await db.commit()
    await callback.message.edit_text(f"🎁 +{tt}🎫 +{td}💎")
PYEOF

systemctl restart tradeall-bot
echo "handlers_user.py заменён, бот перезапущен"
