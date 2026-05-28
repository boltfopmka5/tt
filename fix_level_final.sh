#!/bin/bash

echo "=== ВЫРЕЗАЮ старый /level и ВСТАВЛЯЮ новый ==="

cat > /tmp/fix_level_hard.py << 'EOF'
with open('/opt/bot/handlers_user.py', 'r') as f:
    lines = f.readlines()

# Ищем где начинается функция cmd_level
start = None
end = None
for i, line in enumerate(lines):
    if 'async def cmd_level' in line:
        start = i
    if start is not None and line.strip() == '' and i > start + 5:
        # Ищем конец функции (пустая строка после блока)
        if start is not None:
            # Проверим что следующая строка — декоратор или def
            next_line = lines[i+1] if i+1 < len(lines) else ''
            if next_line.startswith('@') or next_line.startswith('async def') or next_line.startswith('def '):
                end = i
                break

if start and end:
    new_func = '''@router.message(Command("level"))
async def cmd_level(message: types.Message):
    user_id = message.from_user.id
    db = await get_db()
    cursor = await db.execute("SELECT current_exp, total_exp, current_level FROM user_levels WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    if row:
        cur = row[0]
        total = row[1]
        lvl = row[2]
    else:
        cur = 0
        total = 0
        lvl = 1
    ld = LEVELS.get(lvl, LEVELS[max(LEVELS.keys())])
    un = message.from_user.username or message.from_user.first_name
    msg = ld["emoji"] + " " + un + " - " + ld["name"] + " (Lvl " + str(lvl) + ")"
    msg += "\\nXP: " + str(cur) + " | Total: " + str(total)
    await message.answer(msg)

'''
    lines[start:end+1] = [new_func]
    with open('/opt/bot/handlers_user.py', 'w') as f:
        f.writelines(lines)
    print("level - OK")
else:
    print("Не нашёл функцию cmd_level")
EOF

python3 /tmp/fix_level_hard.py

systemctl restart tradeall-bot
echo "=== Готово ==="
