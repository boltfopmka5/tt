#!/bin/bash

echo "=== Исправляю все ошибки в автоответчике ==="

cat > /tmp/fix_autoreply.py << 'EOF'
with open('/opt/bot/auto_reply_bot.py', 'r') as f:
    content = f.read()

# 1. Меняем все parse_mode="Markdown" на parse_mode="HTML" (или убираем)
count = content.count('parse_mode="Markdown"')
content = content.replace('parse_mode="Markdown"', '# parse_mode removed')
print(f"Убрано Markdown: {count} шт.")

# 2. Меняем канал на правильный
content = content.replace('@TradeAll_links', '@TradeAll_free')
content = content.replace('TradeAll_links', 'TradeAll_free')
print("Канал исправлен на @TradeAll_free")

# 3. Меняем юзернейм бота
content = content.replace('@TradeAll_bot', '@TradeAllPay_bot')
content = content.replace('TradeAll_bot', 'TradeAllPay_bot')
print("Бот исправлен на @TradeAllPay_bot")

# 4. Убираем всё Markdown-форматирование из ответов
# Заменяем *текст* на просто текст
import re
content = re.sub(r'\*(.+?)\*', r'\1', content)
content = re.sub(r'`(.+?)`', r'\1', content)
print("Убрано жирное и код")

with open('/opt/bot/auto_reply_bot.py', 'w') as f:
    f.write(content)

print("Готово")
EOF

python3 /tmp/fix_autoreply.py

systemctl restart tradeall-autoreply
echo "=== Автоответчик перезапущен ==="
