cat > /opt/bot/restart_all.sh << 'EOF'
#!/bin/bash
echo "=== Restarting all bots ==="
systemctl restart tradeall-bot
systemctl restart tradeall-autoreply
echo "Done. All bots restarted."
echo ""
systemctl status tradeall-bot --no-pager -l | grep Active
systemctl status tradeall-autoreply --no-pager -l | grep Active
EOF

chmod +x /opt/bot/restart_all.sh
