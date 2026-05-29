cat > /opt/bot/status.sh << 'EOF'
#!/bin/bash
echo "=== TradeAll Status ==="
echo ""
echo "Main Bot:      $(systemctl is-active tradeall-bot)"
echo "Auto Reply:    $(systemctl is-active tradeall-autoreply)"
echo ""
echo "=== Cron ==="
crontab -l 2>/dev/null || echo "Cron не настроен"
echo ""
echo "=== Disk ==="
df -h / | tail -1 | awk '{print "Free: " $4 " / " $2}'
echo ""
echo "=== RAM ==="
free -h | grep Mem | awk '{print "Used: " $3 " / " $2}'
EOF

chmod +x /opt/bot/status.sh
