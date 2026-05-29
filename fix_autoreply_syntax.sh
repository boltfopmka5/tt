#!/bin/bash
echo "=== Исправляю синтаксис автоответчика ==="

sed -i 's/reply, ,/reply,/g' /opt/bot/auto_reply_bot.py
sed -i 's/parse_mode removed, ,//g' /opt/bot/auto_reply_bot.py
sed -i 's/(f"Я автоответчик. Команды работают в основном боте: {MAIN_BOT}", )/(f"Я автоответчик. Команды работают в основном боте: {MAIN_BOT}")/g' /opt/bot/auto_reply_bot.py

systemctl restart tradeall-autoreply
systemctl status tradeall-autoreply --no-pager -l | grep Active
echo "=== Готово ==="
