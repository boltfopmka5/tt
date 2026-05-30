#!/bin/bash
echo "=== Исправляю cron.py и убиваю лишние процессы ==="

# Убить все старые процессы cron.py
pkill -9 -f cron.py
echo "Старые процессы убиты"

# Создать новый cron.py с защитой от повторов
cat > /opt/bot/cron.py << 'PYEOF'
import asyncio
import sys
import subprocess
from datetime import datetime, timedelta
from aiogram import Bot
from config import BOT_TOKEN, CHANNEL_ID
from database import get_db

# Проверка: если уже запущен — выйти
result = subprocess.run(['pgrep', '-f', 'cron.py'], capture_output=True, text=True)
pids = result.stdout.strip().split('\n')
if len(pids) > 2:
    print("cron.py уже запущен, выхожу")
    sys.exit(0)

GROUP_ID = -1003715048435

async def check_expired():
    bot = Bot(token=BOT_TOKEN)
    db = await get_db()
    
    cursor = await db.execute(
        'SELECT user_id FROM users WHERE expire_date < ? AND expire_date IS NOT NULL',
        (datetime.now().isoformat(),)
    )
    expired = await cursor.fetchall()
    
    for (uid,) in expired:
        try:
            await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=uid)
            await asyncio.sleep(0.5)
            await bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=uid)
        except:
            pass
        try:
            await bot.ban_chat_member(chat_id=GROUP_ID, user_id=uid)
            await asyncio.sleep(0.5)
            await bot.unban_chat_member(chat_id=GROUP_ID, user_id=uid)
        except:
            pass
        try:
            await bot.send_message(uid, "Твоя подписка истекла. Продли: /start")
        except:
            pass
        await db.execute('UPDATE users SET expire_date = NULL WHERE user_id = ?', (uid,))
    
    await db.commit()
    
    cursor = await db.execute(
        "SELECT user_id FROM users WHERE expire_date < ? AND expire_date > ? AND total_paid <= 3",
        (datetime.now() + timedelta(hours=12), datetime.now().isoformat())
    )
    trial_ending = await cursor.fetchall()
    
    for (uid,) in trial_ending:
        try:
            await bot.send_message(uid, "Пробный период заканчивается через 12 ч. Продли подписку: /start")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(check_expired())
PYEOF

echo "cron.py обновлён"
echo "Готово"
