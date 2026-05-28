#!/bin/bash

echo "=== Фикс /level ==="
cat > /tmp/fix_level.py << 'EOF'
with open('/opt/bot/handlers_user.py', 'r') as f:
    content = f.read()

old = '''@router.message(Command("level"))
async def cmd_level(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT current_exp, total_exp, current_level FROM user_levels WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    cur, total, lvl = row if row else (0, 0, 1)
    ld = LEVELS.get(lvl, LEVELS[max(LEVELS.keys())])
    un = message.from_user.username or message.from_user.first_name
    await message.answer(f"{ld['emoji']} {un} — {ld['name']} (Уровень {lvl})\\nОпыт: {cur} XP | Всего: {total} XP")'''

new = '''@router.message(Command("level"))
async def cmd_level(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT current_exp, total_exp, current_level FROM user_levels WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    cur, total, lvl = row if row else (0, 0, 1)
    ld = LEVELS.get(lvl, LEVELS[max(LEVELS.keys())])
    un = message.from_user.username or message.from_user.first_name
    text = f"{ld['emoji']} {un} - {ld['name']} (Уровень {lvl})\\nОпыт: {cur} XP | Всего: {total} XP"
    await message.answer(text)'''

content = content.replace(old, new)
with open('/opt/bot/handlers_user.py', 'w') as f:
    f.write(content)
print("level - OK")
EOF
python3 /tmp/fix_level.py

echo "=== Фикс /support ==="
cat > /tmp/fix_support.py << 'EOF'
with open('/opt/bot/handlers_user.py', 'r') as f:
    content = f.read()

old_support = '''@router.message(Command("support"))
async def cmd_support(message: types.Message):
    await message.answer("📞 *Поддержка TradeAll*\\n\\nПо всем вопросам: @TradeAll_Support\\n\\nИли напиши в тему «Поддержка» в группе.", parse_mode="Markdown")'''

new_support = '''@router.message(Command("support"))
async def cmd_support(message: types.Message):
    text = "📞 Поддержка TradeAll\\n\\nПо всем вопросам: @TradeAll_Support\\n\\nИли напиши в тему «Поддержка» в группе."
    await message.answer(text)'''

content = content.replace(old_support, new_support)

old_callback = '''@router.callback_query(lambda c: c.data == "support")
async def cmd_support_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📞 *Поддержка TradeAll*\\n\\nПо всем вопросам: @TradeAll_Support\\n\\nОтвечаю в течение часа.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back_main")]])
    )'''

new_callback = '''@router.callback_query(lambda c: c.data == "support")
async def cmd_support_callback(callback: types.CallbackQuery):
    text = "📞 Поддержка TradeAll\\n\\nПо всем вопросам: @TradeAll_Support\\n\\nОтвечаю в течение часа."
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back_main")]])
    )'''

content = content.replace(old_callback, new_callback)
with open('/opt/bot/handlers_user.py', 'w') as f:
    f.write(content)
print("support - OK")
EOF
python3 /tmp/fix_support.py

echo "=== Добавляю /help для группы ==="
cat > /tmp/add_help.py << 'EOF'
with open('/opt/bot/handlers_user.py', 'r') as f:
    content = f.read()

help_func = '''
@router.message(Command("help"))
async def cmd_help(message: types.Message):
    if message.chat.type == "private":
        return
    text = """📋 Доступные команды в группе:

/rules — правила клуба
/top — топ рефереров
/support — контакты поддержки
/level — твой уровень и звание
/lottery — информация о розыгрыше
/help — этот список

Команды в личке с ботом:
/start — главное меню
/referral — партнёрский кабинет
/profile — твоя статистика
/achievements — достижения
/tasks — ежедневные задания"""
    await message.answer(text)'''

content = content.replace(
    '@router.message(Command("support"))',
    help_func + '\n\n@router.message(Command("support"))'
)

with open('/opt/bot/handlers_user.py', 'w') as f:
    f.write(content)
print("help - OK")
EOF
python3 /tmp/add_help.py

echo "=== Меняю розыгрыш на раз в 2 недели ==="
cat > /tmp/fix_lottery_biweekly.py << 'EOF'
with open('/opt/bot/handlers_user.py', 'r') as f:
    content = f.read()

old = '''@router.message(Command("lottery"))
async def cmd_lottery(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT COALESCE(lottery_tickets, 0) FROM users WHERE user_id = ?', (user_id,))
    tickets = (await cursor.fetchone())[0]
    days_to_sun = (6 - datetime.now().weekday()) % 7 or 7
    next_draw = (datetime.now() + timedelta(days=days_to_sun)).replace(hour=20, minute=0, second=0)
    await message.answer(f"🎰 *Розыгрыш*\\n\\n📅 {next_draw.strftime('%d.%m.%Y 20:00')}\\n🎫 Билетов: {tickets}\\n\\nПризы: 30/14/7 дн.", parse_mode="Markdown")'''

new = '''@router.message(Command("lottery"))
async def cmd_lottery(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT COALESCE(lottery_tickets, 0) FROM users WHERE user_id = ?', (user_id,))
    tickets = (await cursor.fetchone())[0]
    today = datetime.now()
    week_number = today.isocalendar()[1]
    if week_number % 2 == 0:
        days_to_draw = (14 - today.weekday()) % 14
    else:
        days_to_draw = (7 - today.weekday()) % 7
    if days_to_draw == 0:
        days_to_draw = 14 if week_number % 2 == 1 else 7
    next_draw = today + timedelta(days=days_to_draw)
    next_draw = next_draw.replace(hour=20, minute=0, second=0)
    text = f"🎰 Розыгрыш раз в 2 недели\\n\\n📅 Следующий: {next_draw.strftime('%d.%m.%Y 20:00')}\\n🎫 Твои билеты: {tickets}\\n\\nПризы: 30/14/7 дней подписки"
    await message.answer(text)'''

content = content.replace(old, new)
with open('/opt/bot/handlers_user.py', 'w') as f:
    f.write(content)
print("lottery - OK")
EOF
python3 /tmp/fix_lottery_biweekly.py

echo "=== Чищу экранирование ==="
sed -i 's/\\"/"/g' /opt/bot/handlers_user.py
sed -i "s/\\\'/'/g" /opt/bot/handlers_user.py

echo "=== Перезапуск бота ==="
systemctl restart tradeall-bot
echo "=== Готово ==="
