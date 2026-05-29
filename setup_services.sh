#!/bin/bash
echo "=== Установка systemd сервисов TradeAll ==="

# Основной бот
cat > /etc/systemd/system/tradeall-bot.service << 'EOF'
[Unit]
Description=TradeAll Main Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/bot
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Автоответчик
cat > /etc/systemd/system/tradeall-autoreply.service << 'EOF'
[Unit]
Description=TradeAll Auto Reply Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/bot
ExecStart=/usr/bin/python3 auto_reply_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Применить
systemctl daemon-reload

# Включить автозапуск при старте сервера
systemctl enable tradeall-bot
systemctl enable tradeall-autoreply

# Запустить
systemctl start tradeall-bot
systemctl start tradeall-autoreply

# Статус
echo ""
echo "=== Статус ==="
systemctl status tradeall-bot --no-pager -l | grep Active
systemctl status tradeall-autoreply --no-pager -l | grep Active

echo ""
echo "=== Готово ==="
echo "start_all.sh и stop_all.sh теперь работают"
