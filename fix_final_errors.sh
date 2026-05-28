#!/bin/bash

echo "=== Полностью переписываю /lottery и /level ==="

cat > /tmp/fix_final.py << 'EOF'
with open('/opt/bot/handlers_user.py', 'r') as f:
    content = f.read()

# ===== /lottery =====
old_lottery = '''@router.message(Command("lottery"))
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

new_lottery = '''@router.message(Command("lottery"))
async def cmd_lottery(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT COALESCE(lottery_tickets, 0) FROM users WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    tickets = row[0] if row else 0
    from datetime import date
    today = date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    next_sunday = today + timedelta(days=days_until_sunday)
    next_draw_str = next_sunday.strftime("%d.%m.%Y")
    text = (
        "🎰 Розыгрыш раз в 2 недели\\n\\n"
        "📅 Следующий: " + next_draw_str + " 20:00\\n"
        "🎫 Твои билеты: " + str(tickets) + "\\n\\n"
        "Призы: 30/14/7 дней подписки"
    )
    await message.answer(text)'''

content = content.replace(old_lottery, new_lottery)

# ===== /level =====
old_level = '''@router.message(Command("level"))
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

new_level = '''@router.message(Command("level"))
async def cmd_level(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute('SELECT current_exp, total_exp, current_level FROM user_levels WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    if row:
        cur, total, lvl = row
    else:
        cur, total, lvl = 0, 0, 1
    ld = LEVELS.get(lvl, LEVELS[max(LEVELS.keys())])
    un = message.from_user.username or message.from_user.first_name
    text = ld['emoji'] + " " + str(un) + " - " + ld['name'] + " (Уровень " + str(lvl) + ")\\nОпыт: " + str(cur) + " XP | Всего: " + str(total) + " XP"
    await message.answer(text)'''

content = content.replace(old_level, new_level)

with open('/opt/bot/handlers_user.py', 'w') as f:
    f.write(content)

print("Готово")
EOF

python3 /tmp/fix_final.py

echo "=== Перезапуск ==="
systemctl restart tradeall-bot
echo "=== Готово ==="
