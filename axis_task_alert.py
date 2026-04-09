import time
import requests
import os
from flask import Flask
from threading import Thread

# ==========================================
# 1. CẤU HÌNH CƠ BẢN
# ==========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8655926285:AAHuLlGex98_UiAqpKVdDBBrNvxrV6sodKw')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '1246404230')
PORT = int(os.getenv('PORT', 8080))

# Trí nhớ của bot
seen_task_ids = set()
notified_600_tasks = set()
latest_tasks_cache = []  # CACHE: Giúp lệnh /slots trả lời tức thì
is_website_down = False

app = Flask(__name__)
@app.route('/')
def home(): return "Bot đang chạy siêu tốc trên Render!"

# ==========================================
# 2. HÀM GIAO TIẾP TELEGRAM
# ==========================================
def send_msg(text):
    """Hàm gửi tin nhắn rút gọn"""
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, 
                      timeout=5)
    except: pass

def telegram_listener():
    """Luồng lắng nghe lệnh từ bạn (Đã tối ưu tốc độ)"""
    last_id = 0
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                               params={"offset": last_id + 1, "timeout": 30}, timeout=35).json()
            
            for update in res.get("result", []):
                last_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "").lower()
                
                # Chỉ nhận lệnh từ đúng ID của Victor
                if str(msg.get("chat", {}).get("id")) == TELEGRAM_CHAT_ID:
                    
                    if text in ["/status", "check"]:
                        send_msg(f"✅ <b>BÁO CÁO:</b> Bot vẫn đang canh gác!\n📡 Trạng thái Axis: {'🔴 Đang lag/sập' if is_website_down else '🟢 Rất mượt'}")
                    
                    elif text in ["/slots", "slots"]:
                        # ĐỌC TỪ CACHE -> TRẢ LỜI NGAY LẬP TỨC KHÔNG CẦN CHỜ AXIS
                        if not latest_tasks_cache:
                            send_msg("⚠️ <b>HIỆN TẠI TRẮNG BẢNG:</b> Không có task nào (hoặc web đang sập).")
                        else:
                            out = "📊 <b>TÌNH TRẠNG SLOT THỰC TẾ:</b>\n\n"
                            for t in latest_tasks_cache:
                                name = t.get('title') or t.get('name') or 'Task'
                                done = int(t.get('slot_completed', 0))
                                total = int(t.get('slot') or t.get('total_slots') or t.get('limit') or 0)
                                prog = f"{done}/{total}" if total > 0 else f"{done}/?"
                                out += f"🔹 <b>{name}</b>\n   └ Tiến độ: <b>{prog}</b> slots\n\n"
                            send_msg(out.strip())
        except:
            time.sleep(2)

# ==========================================
# 3. LUỒNG LÀM VIỆC CHÍNH (QUÉT TASK 20S)
# ==========================================
def main_loop():
    global is_website_down, latest_tasks_cache, seen_task_ids, notified_600_tasks
    fails = 0
    first_run = True
    
    print("Khởi động hệ thống check task...")
    send_msg("🚀 <b>BOT ĐÃ ON:</b> Mã nguồn đã được tối ưu siêu tốc. Tốc độ quét: 20s.")
    
    while True:
        try:
            res = requests.get('https://hub.axisrobotics.ai/api/tasks',
                               params={'sort_order': 'desc', 'status': 'active', 'page': '1', 'per_page': '9'},
                               headers={'user-agent': 'Mozilla/5.0'}, timeout=15)
            res.raise_for_status()
            
            # --- XỬ LÝ KHI WEB SỐNG LẠI ---
            if is_website_down:
                send_msg("🟢 <b>TIN VUI:</b> Web Axis đã mượt trở lại!")
                is_website_down = False
            fails = 0
            
            # Lấy data và LỌC BỎ NGAY TASK 20 từ vòng gửi xe
            raw_tasks = res.json().get('tasks', [])
            valid_tasks = [t for t in raw_tasks if str(t.get('id') or t.get('_id')) not in ["20", "None"]]
            
            # Lưu vào Cache cho lệnh /slots dùng
            latest_tasks_cache = valid_tasks
            
            new_msg, hot_msg = [], []
            for t in valid_tasks:
                tid = str(t.get('id') or t.get('_id'))
                name = t.get('title') or t.get('name') or 'Task'
                done = int(t.get('slot_completed', 0))
                total = int(t.get('slot') or t.get('total_slots') or t.get('limit') or 0)
                
                prog_text = f"{done}/{total}" if total > 0 else f"{done}"
                link = f"https://hub.axisrobotics.ai/action?id={tid}"
                
                # 1. Bắt task mới
                if tid not in seen_task_ids:
                    seen_task_ids.add(tid)
                    if not first_run: new_msg.append(f"🔹 <a href='{link}'>{name}</a>")
                
                # 2. Bắt task 600 slot
                if done >= 600 and tid not in notified_600_tasks:
                    notified_600_tasks.add(tid)
                    if not first_run: hot_msg.append(f"🔥 <a href='{link}'>{name}</a> <b>({prog_text} slots)</b>")
            
            # Bắn thông báo nếu có
            if new_msg: send_msg("📢 <b>CÓ TASK MỚI:</b>\n\n" + "\n".join(new_msg))
            if hot_msg: send_msg("⚠️ <b>HOT: TASK ĐẠT >600 SLOT:</b>\n\n" + "\n".join(hot_msg))
            
            first_run = False
            
        except Exception as e:
            fails += 1
            if fails == 3 and not is_website_down:
                send_msg("🔴 <b>CẢNH BÁO:</b> Web Axis đang sập/lag!")
                is_website_down = True
                latest_tasks_cache = [] # Xóa cache khi sập
                
        time.sleep(20)

# ==========================================
# 4. KHỞI ĐỘNG
# ==========================================
if __name__ == "__main__":
    # Bật web giả cho Render
    Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()
    # Bật luồng nghe lệnh Telegram
    Thread(target=telegram_listener, daemon=True).start()
    # Chạy vòng lặp quét task
    main_loop()
