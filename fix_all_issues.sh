#!/bin/bash

echo "=== Исправляю рефералов и админку ==="

cat > /tmp/fix_all.py << 'EOF'
with open('/opt/bot/handlers_user.py', 'r') as f:
    content = f.read()

# ===== Фикс рефералов: добавляем вывод в консоль =====
old_ref = '''    if ref_code and not exists:
        cursor = await db.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref_code,))
        ref = await cursor.fetchone()
        if ref and ref[0] != user_id:
            await db.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (ref[0], user_id))
            await db.commit()
            await add_exp(ref[0], "referral_register")
            await update_lottery_tickets(ref[0])
            await update_task_progress(ref[0], "invite_1", 1)
            await update_task_progress(ref[0], "invite_3", 1)'''

new_ref = '''    if ref_code and not exists:
        cursor = await db.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref_code,))
        ref = await cursor.fetchone()
        if ref and ref[0] != user_id:
            print(f"[REF] Новый реферал: {ref[0]} пригласил {user_id}")
            await db.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (ref[0], user_id))
            await db.commit()
            await process_referral(ref[0], user_id)
            await add_exp(ref[0], "referral_register")
            await update_lottery_tickets(ref[0])
            await update_task_progress(ref[0], "invite_1", 1)
            await update_task_progress(ref[0], "invite_3", 1)
            print(f"[REF] process_referral выполнен")
        else:
            print(f"[REF] ref_code={ref_code}, ref={ref}, user_id={user_id} - условие не сработало")'''

if old_ref in content:
    content = content.replace(old_ref, new_ref)
    print("Рефералы - OK")
else:
    print("Не нашёл блок рефералов, проверь вручную")

with open('/opt/bot/handlers_user.py', 'w') as f:
    f.write(content)

# ===== Фикс админки =====
with open('/opt/bot/handlers_admin.py', 'r') as f:
    admin = f.read()

old_adm = '''    text = f"📊 Статистика\\n\\n👥 Всего: {total}\\n✅ Активных: {active}\\n💰 Выручка: {rev:.2f} USDT\\n📅 За месяц: {mp} пл. / {mr:.2f} USDT"
    await callback.message.edit_text(text, reply_markup=admin_kb())'''

new_adm = '''    text = f"📊 Статистика\\n\\n👥 Всего: {total}\\n✅ Активных: {active}\\n💰 Выручка: {rev:.2f} USDT\\n📅 За месяц: {mp} пл. / {mr:.2f} USDT"
    try:
        await callback.message.edit_text(text, reply_markup=admin_kb())
    except:
        await callback.answer("Статистика не изменилась", show_alert=True)'''

admin = admin.replace(old_adm, new_adm)

with open('/opt/bot/handlers_admin.py', 'w') as f:
    f.write(admin)
print("Админка - OK")
EOF

python3 /tmp/fix_all.py

systemctl restart tradeall-bot
echo "=== Готово ==="
