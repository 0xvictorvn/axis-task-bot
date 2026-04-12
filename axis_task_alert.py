import time
import requests
import os
from flask import Flask
from threading import Thread

# ==========================================
# 1. CẤU HÌNH & TRẠNG THÁI HỆ THỐNG
# ==========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8655926285:AAHuLlGex98_UiAqpKVdDBBrNvxrV6sodKw')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '1246404230')
PORT = int(os.getenv('PORT', 8080))

# Trí nhớ hệ thống
seen_task_ids = set()
notified_hot_tasks = set()
latest_tasks_cache = []  
is_website_down = False

# Cấu hình động từ Telegram
scan_speed = 20      
alert_threshold = 600 
end_alert_enabled = True # MẶC ĐỊNH BẬT: Báo khi task biến mất (Full)

app = Flask(__name__)
@app.route('/')
def home(): return "Hệ thống Axis Radar - Hoạt động tối đa công suất!"

# ==========================================
# 2. HÀM GIAO TIẾP TELEGRAM
# ==========================================
def send_msg(text):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, 
                      timeout=5)
    except: pass

def telegram_listener():
    global scan_speed, alert_threshold, is_website_down, notified_hot_tasks, end_alert_enabled
    last_id = 0
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                               params={"offset": last_id + 1, "timeout": 30}, timeout=35).json()
            
            for update in res.get("result", []):
                last_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "").lower()
                
                # Chỉ xử lý lệnh từ đúng ID của Victor
                if str(msg.get("chat", {}).get("id")) != TELEGRAM_CHAT_ID: continue
                    
                # 1. STATUS
                if text in ["/status", "check"]:
                    al_str = f"<b>{alert_threshold}</b> slots" if alert_threshold > 0 else "OFF"
                    en_str = "BẬT ✅" if end_alert_enabled else "TẮT ❌"
                    send_msg(f"📝 <b>TRẠNG THÁI:</b>\n⏱ Quét: {scan_speed}s | 🔥 Báo động: {al_str}\n🏁 Báo kết thúc: {en_str}\n📡 Axis: {'🔴 Lag' if is_website_down else '🟢 OK'}")
                
                # 2. SLOTS (Realtime Cache)
                elif text in ["/slots", "slots"]:
                    if not latest_tasks_cache: send_msg("⚠️ <b>HIỆN TẠI:</b> Không có task nào trên web.")
                    else:
                        out = "📊 <b>SLOT THỰC TẾ:</b>\n\n"
                        for t in latest_tasks_cache:
                            tid = str(t.get('id') or t.get('_id'))
                            name = t.get('title') or t.get('name') or 'Task'
                            done = int(t.get('slot_completed', 0))
                            total = int(t.get('slot') or t.get('total_slots') or t.get('limit') or 0)
                            prog = f"{done}/{total}" if total > 0 else f"{done}/?"
                            link = f"https://hub.axisrobotics.ai/action?id={tid}"
                            out += f"🔹 <a href='{link}'><b>{name}</b></a>\n   └ <b>{prog}</b> slots\n\n"
                        send_msg(out.strip())
                            
                # 3. SET SPEED, ALERT, END_ALERT
                elif text.startswith("/speed ") or text.startswith("speed "): 
                    try:
                        scan_speed = max(10, int(text.split()[1]))
                        send_msg(f"⚡ Tốc độ mới: <b>{scan_speed}s/lần</b>")
                    except: send_msg("⚠️ Lỗi cú pháp! Gõ: <b>/speed 15</b>")
                        
                elif text.startswith("/alert ") or text.startswith("alert "): 
                    try:
                        val_str = text.split()[1]
                        alert_threshold = 0 if val_str == "off" else int(val_str)
                        notified_hot_tasks.clear()
                        if alert_threshold == 0: send_msg("🔕 Đã tắt báo động slot.")
                        else: send_msg(f"🔔 Mốc báo động: <b>{alert_threshold} slots</b>")
                    except: send_msg("⚠️ Lỗi cú pháp! Gõ: <b>/alert 800</b> hoặc <b>/alert 0</b>")
                        
                elif text in ["/end_alert on", "end on"]: 
                    end_alert_enabled = True; send_msg("✅ Đã bật báo Task kết thúc.")
                elif text in ["/end_alert off", "end off"]: 
                    end_alert_enabled = False; send_msg("❌ Đã tắt báo Task kết thúc.")

        except: time.sleep(2)

# ==========================================
# 3. LOGIC QUÉT VÀ SO SÁNH (KEY LOGIC)
# ==========================================
def main_loop():
    global is_website_down, latest_tasks_cache, seen_task_ids, notified_hot_tasks, scan_speed, alert_threshold, end_alert_enabled
    fails, first_run = 0, True
    send_msg("🚀 <b>BOT ĐÃ ON:</b> Mã nguồn Tối Thượng đã chạy! Hãy gõ /status để xem.")
    
    while True:
        try:
            res = requests.get('https://hub.axisrobotics.ai/api/tasks',
                               params={'sort_order': 'desc', 'status': 'active', 'page': '1', 'per_page': '9'},
                               headers={'user-agent': 'Mozilla/5.0'}, timeout=15)
            res.raise_for_status()
            
            if is_website_down: send_msg("🟢 <b>TIN VUI:</b> Web Axis đã mượt trở lại!"); is_website_down = False
            fails = 0
            
            raw_data = res.json().get('tasks', [])
            current_tasks = [t for t in raw_data if str(t.get('id') or t.get('_id')) not in ["20", "99", "293", "None"]]
            current_ids = {str(t.get('id') or t.get('_id')) for t in current_tasks}
            
            # --- LOGIC: PHÁT HIỆN TASK BIẾN MẤT VÀ DỌN RÁC ---
            if not first_run:
                for old_task in latest_tasks_cache:
                    oid = str(old_task.get('id') or old_task.get('_id'))
                    if oid not in current_ids:
                        if end_alert_enabled:
                            name = old_task.get('title') or old_task.get('name') or 'Task'
                            last_slot = old_task.get('slot_completed', '?')
                            total = old_task.get('slot') or old_task.get('total_slots') or old_task.get('limit') or '?'
                            send_msg(f"🏁 <b>TASK ĐÃ KẾT THÚC (FULL):</b>\n🔹 <b>{name}</b>\n└ Ghi nhận cuối: <b>{last_slot}/{total}</b>")
                        
                        # DỌN RÁC BỘ NHỚ
                        seen_task_ids.discard(oid)
                        notified_hot_tasks.discard(oid)

            # Xử lý thông báo Task mới và Hot Task
            new_msg, hot_msg = [], []
            for t in current_tasks:
                tid = str(t.get('id') or t.get('_id'))
                name = t.get('title') or t.get('name') or 'Task'
                done = int(t.get('slot_completed', 0))
                total = int(t.get('slot') or t.get('total_slots') or t.get('limit') or 0)
                link = f"https://hub.axisrobotics.ai/action?id={tid}"
                
                if tid not in seen_task_ids:
                    seen_task_ids.add(tid); 
                    if not first_run: new_msg.append(f"🔹 <a href='{link}'><b>{name}</b></a>")
                
                if alert_threshold > 0 and done >= alert_threshold and tid not in notified_hot_tasks:
                    notified_hot_tasks.add(tid); 
                    if not first_run: hot_msg.append(f"🔥 <a href='{link}'><b>{name}</b></a> <b>({done}/{total})</b>")
            
            if new_msg: send_msg("📢 <b>TASK MỚI LÊN KỆ:</b>\n\n" + "\n".join(new_msg))
            if hot_msg: send_msg(f"⚠️ <b>VƯỢT NGƯỠNG {alert_threshold} SLOTS:</b>\n\n" + "\n".join(hot_msg))
            
            latest_tasks_cache = current_tasks # Cập nhật cache cho lần sau
            first_run = False
        except:
            fails += 1
            if fails >= 3 and not is_website_down: send_msg("🔴 Web Axis Lag/Sập!"); is_website_down = True
            
        time.sleep(scan_speed)

# ==========================================
# 4. KHỞI ĐỘNG
# ==========================================
if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()
    Thread(target=telegram_listener, daemon=True).start()
    main_loop()
