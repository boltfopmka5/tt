#!/bin/bash
cat > /tmp/patch_terms.py << 'EOF'
import re

with open('/opt/bot/handlers_user.py', 'r') as f:
    content = f.read()

# Заменяем buy_sub
old_sub = """@router.callback_query(lambda c: c.data == "buy_sub")
async def buy_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    unique = round(PRICE_USDT + random.randint(1, 99) / 100, 2)
    db = await get_db()
    await db.execute('INSERT INTO users (user_id, unique_amount) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET unique_amount = ?',
                    (user_id, unique, unique))
    await db.commit()
    await callback.message.edit_text(
        f"💎 *Подписка — {PRICE_USDT} USDT/мес*\\n\\n"
        f"Отправьте *ровно {unique} USDT*:\\n\\n"
        f"🔹 TON: `{TON_WALLET}`\\n"
        f"🔹 TRC20: `{TRC20_WALLET}`\\n\\n"
        f"📄 /terms",
        parse_mode="Markdown",
        reply_markup=payment_methods_kb("check_sub")
    )"""

new_sub = """@router.callback_query(lambda c: c.data == "buy_sub")
async def buy_sub(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📄 *Перед оплатой ознакомься с условиями:*\\n\\n"
        "• Трейдинг — это риск потери капитала\\n"
        "• Бот даёт аналитику, а не гарантии\\n"
        "• Вся ответственность на тебе\\n"
        "• Полные условия: /terms\\n"
        "• Правила клуба: /rules\\n\\n"
        "Оплачивая, ты принимаешь эти условия.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=\\"✅ Принимаю и оплатить\\", callback_data=\\"buy_sub_confirm\\")],
            [InlineKeyboardButton(text=\\"◀️ Назад\\", callback_data=\\"back_main\\")],
        ])
    )

@router.callback_query(lambda c: c.data == "buy_sub_confirm")
async def buy_sub_confirm(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    unique = round(PRICE_USDT + random.randint(1, 99) / 100, 2)
    db = await get_db()
    await db.execute('INSERT INTO users (user_id, unique_amount) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET unique_amount = ?',
                    (user_id, unique, unique))
    await db.commit()
    await callback.message.edit_text(
        f"💎 *Подписка — {PRICE_USDT} USDT/мес*\\n\\n"
        f"Отправьте *ровно {unique} USDT*:\\n\\n"
        f"🔹 TON: `{TON_WALLET}`\\n"
        f"🔹 TRC20: `{TRC20_WALLET}`\\n\\n"
        f"📄 /terms",
        parse_mode="Markdown",
        reply_markup=payment_methods_kb("check_sub")
    )"""

content = content.replace(old_sub, new_sub)

# Заменяем buy_trial
old_trial = """@router.callback_query(lambda c: c.data == "buy_trial")
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
        f"🔑 *Пробный период — {TRIAL_PRICE} USDT на {TRIAL_DAYS} дня*\\n\\n"
        f"Отправьте *ровно {unique} USDT*:\\n\\n"
        f"🔹 TON: `{TON_WALLET}`\\n"
        f"🔹 TRC20: `{TRC20_WALLET}`\\n\\n"
        f"📄 /terms",
        parse_mode="Markdown",
        reply_markup=payment_methods_kb("check_trial")
    )"""

new_trial = """@router.callback_query(lambda c: c.data == "buy_trial")
async def buy_trial(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT trial_used FROM users WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    if row and row[0]:
        await callback.answer("Ты уже брал пробный период!", show_alert=True)
        return
    await callback.message.edit_text(
        "📄 *Перед оплатой ознакомься с условиями:*\\n\\n"
        "• Трейдинг — это риск потери капитала\\n"
        "• Бот даёт аналитику, а не гарантии\\n"
        "• Вся ответственность на тебе\\n"
        "• Полные условия: /terms\\n"
        "• Правила клуба: /rules\\n\\n"
        "Оплачивая, ты принимаешь эти условия.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=\\"✅ Принимаю и оплатить\\", callback_data=\\"buy_trial_confirm\\")],
            [InlineKeyboardButton(text=\\"◀️ Назад\\", callback_data=\\"back_main\\")],
        ])
    )

@router.callback_query(lambda c: c.data == "buy_trial_confirm")
async def buy_trial_confirm(callback: types.CallbackQuery):
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
        f"🔑 *Пробный период — {TRIAL_PRICE} USDT на {TRIAL_DAYS} дня*\\n\\n"
        f"Отправьте *ровно {unique} USDT*:\\n\\n"
        f"🔹 TON: `{TON_WALLET}`\\n"
        f"🔹 TRC20: `{TRC20_WALLET}`\\n\\n"
        f"📄 /terms",
        parse_mode="Markdown",
        reply_markup=payment_methods_kb("check_trial")
    )"""

content = content.replace(old_trial, new_trial)

# Добавляем импорт InlineKeyboardMarkup
if "from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton" not in content:
    content = content.replace(
        "from aiogram import Router, types, F, Bot",
        "from aiogram import Router, types, F, Bot\nfrom aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton"
    )

with open('/opt/bot/handlers_user.py', 'w') as f:
    f.write(content)

print("Готово")
EOF

python3 /tmp/patch_terms.py
systemctl restart tradeall-bot
echo "Бот перезапущен"
