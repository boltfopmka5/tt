#!/bin/bash

echo "=== Исправляю реферальные начисления ==="

cat > /tmp/fix_ref.py << 'EOF'
with open('/opt/bot/handlers_user.py', 'r') as f:
    content = f.read()

# Убираем начисление за простой переход
old = '''    if ref_code and not exists:
        cursor = await db.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref_code,))
        ref = await cursor.fetchone()
        if ref and ref[0] != user_id:
            await db.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (ref[0], user_id))
            await db.commit()
            await process_referral(ref[0], user_id)
            await add_exp(ref[0], "referral_register")
            await update_lottery_tickets(ref[0])
            try:
                await message.bot.send_message(ref[0], f"🎉 Новый реферал! +{REFERRAL_BONUS_TRIAL} дн.")
            except:
                pass'''

new = '''    if ref_code and not exists:
        cursor = await db.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref_code,))
        ref = await cursor.fetchone()
        if ref and ref[0] != user_id:
            await db.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (ref[0], user_id))
            await db.commit()
            await add_exp(ref[0], "referral_register")
            await update_lottery_tickets(ref[0])'''

content = content.replace(old, new)

# Правильные цифры в тексте рефералки
old_text = '''f"+{REFERRAL_BONUS_TRIAL} дн. за пробник друга\\n+{REFERRAL_BONUS_DAYS} дн. за подписку друга\\nДни продлевают твою подписку."'''

new_text = '''"+3 дн. за пробник друга\\n+7 дн. за полную подписку друга\\nДни продлевают твою подписку."'''

content = content.replace(old_text, new_text)

with open('/opt/bot/handlers_user.py', 'w') as f:
    f.write(content)
print("handlers_user.py - OK")

# Исправляем config.py
with open('/opt/bot/config.py', 'r') as f:
    config = f.read()

config = config.replace('REFERRAL_BONUS_DAYS = 7', 'REFERRAL_BONUS_DAYS = 7')
config = config.replace('REFERRAL_BONUS_TRIAL = 3', 'REFERRAL_BONUS_TRIAL = 3')

# Убеждаемся что process_referral использует правильные дни
with open('/opt/bot/referral.py', 'r') as f:
    ref = f.read()

# Там уже правильно: TRIAL для пробника, DAYS для полной
# Просто проверяем что в process_payment правильный is_trial
with open('/opt/bot/handlers_user.py', 'r') as f:
    content = f.read()

# Ищем process_payment и проверяем что is_trial правильно передаётся
if 'await process_referral(ref[0], user_id, is_trial)' in content:
    print("process_referral - OK (is_trial передаётся)")
else:
    print("WARN: process_referral не найден")

EOF

python3 /tmp/fix_ref.py

systemctl restart tradeall-bot
echo "=== Готово ==="
