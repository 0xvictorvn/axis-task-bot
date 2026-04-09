import time
import requests
import os
from flask import Flask
from threading import Thread

# ==========================================
# PHẦN 1: CẤU HÌNH & TRÍ NHỚ CỦA BOT
# ==========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8655926285:AAHuLlGex98_UiAqpKVdDBBrNvxrV6sodKw')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '1246404230')
PORT = int(os.getenv('PORT', 8080)) 

seen_task_ids = set()           # Nhớ task mới
notified_600_tasks = set()      # Nhớ task đã đạt 600 slot

is_website_down = False
failed_attempts = 0
MAX_FAILURES = 3 

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot đang chạy cực mượt trên Render!"

def run_server():
    app.run(host='0.0.0.0', port=PORT)

# ==========================================
# PHẦN 2: HÀM GỬI & NHẬN TIN NHẮN TELEGRAM
# ==========================================
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def check_telegram_commands():
    last_update_id = 0
    print("Đã bật bộ lắng nghe lệnh Telegram...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 30}
            response = requests.get(url, params=params, timeout=35).json()

            if "result" in response:
                for update in response["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].lower()
                        chat_id = str(update["message"]["chat"]["id"])

                        if chat_id == TELEGRAM_CHAT_ID:
                            if text == "/status" or text == "check":
                                uptime_msg = "✅ <b>BÁO CÁO:</b> Axis Task Alert Bot vẫn đang thức!\n"
                                uptime_msg += f"📡 Trạng thái Axis: {'🔴 Đang lag/sập' if is_website_down else '🟢 Rất mượt'}"
                                send_telegram_message(uptime_msg)
                            
                            # --- LỆNH KIỂM TRA SLOT HIỆN TẠI ---
                            elif text == "/slots" or text == "slots":
                                raw_tasks = get_axis_tasks()
                                
                                # BƯỚC LỌC ĐẦU TIÊN: Lấy ra các task hợp lệ (Khác 20)
                                valid_tasks = []
                                for t in raw_tasks:
                                    tid = str(t.get('id') or t.get('_id'))
                                    if tid and tid != "20":
                                        valid_tasks.append(t)
                                
                                # Xử lý trường hợp "Trắng bảng" sau khi đã lọc
                                if not valid_tasks:
                                    send_telegram_message("⚠️ <b>HIỆN TẠI:</b> Không có task nào đang mở trên Axis lúc này.")
                                else:
                                    slot_msg = "📊 <b>TÌNH TRẠNG SLOT THỰC TẾ:</b>\n\n"
                                    for task in valid_tasks:
                                        name = task.get('title') or task.get('name') or 'Task không tên'
                                        completed = int(task.get('slot_completed', 0))
                                        
                                        # Lấy chính xác biến "slot" dựa trên JSON thực tế
                                        total = int(task.get('slot') or task.get('total_slots') or task.get('limit') or 0)
                                        
                                        if total > 0:
                                            slot_msg += f"🔹 <b>{name}</b>\n   └ Tiến độ: <b>{completed}/{total}</b> slots\n\n"
                                        else:
                                            slot_msg += f"🔹 <b>{name}</b>\n   └ Tiến độ: <b>{completed}/?</b> slots\n\n"
                                            
                                    send_telegram_message(slot_msg.strip())
        except:
            pass
        time.sleep(2)

# ==========================================
# PHẦN 3: LẤY DỮ LIỆU & XỬ LÝ TASK
# ==========================================
def get_axis_tasks():
    global is_website_down, failed_attempts
    url = 'https://hub.axisrobotics.ai/api/tasks'
    params = {'sort_order': 'desc', 'status': 'active', 'search': '', 'page': '1', 'per_page': '9'}
    headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        if is_website_down:
            send_telegram_message("🟢 <b>TIN VUI:</b> Web Axis đã mượt trở lại! Bot tiếp tục làm việc.")
            is_website_down = False
            
        failed_attempts = 0 
        return response.json().get('tasks', [])
    except Exception as e:
        failed_attempts += 1
        print(f"⚠️ Cảnh báo: Lần {failed_attempts}/{MAX_FAILURES} web Axis lag ({e})")
        if failed_attempts == MAX_FAILURES and not is_website_down:
            send_telegram_message("🔴 <b>CẢNH BÁO:</b> Web Axis đang bị sập! Bot sẽ im lặng chờ web phục hồi.")
            is_website_down = True
        return []

def bot_thong_bao_task():
    global seen_task_ids, notified_600_tasks
    is_first_run = True 
    print("Bắt đầu khởi chạy vòng lặp check task (20s/lần)...")
    send_telegram_message("🚀 <b>BOT ĐÃ ON:</b> Hệ thống đã khởi động. Tốc độ: 20s/quét.")
    
    while True:
        try:
            tasks = get_axis_tasks()
            new_tasks_found, tasks_hit_600 = [], []

            for task in tasks:
                task_id = str(task.get('id') or task.get('_id'))
                
                # --- CHẶN ĐỨNG TASK DEMO 20 TẠI ĐÂY ---
                if task_id == "20" or task_id == "None":
                    continue 
                
                task_name = task.get('title') or task.get('name') or 'Task không tên'
                slot_completed = int(task.get('slot_completed', 0))
                total_slots = int(task.get('slot') or task.get('total_slots') or task.get('limit') or 0)
                
                slot_text = f"{slot_completed}/{total_slots}" if total_slots > 0 else f"{slot_completed}"
                task_link = f"https://hub.axisrobotics.ai/action?id={task_id}"
                
                # 1. Kiểm tra task mới
                if task_id not in seen_task_ids:
                    seen_task_ids.add(task_id) 
                    if not is_first_run:
                        new_tasks_found.append(f"🔹 <a href='{task_link}'>{task_name}</a>")
                        
                # 2. Kiểm tra mốc 600 slot
                if slot_completed >= 600 and task_id not in notified_600_tasks:
                    notified_600_tasks.add(task_id)
                    if not is_first_run:
                        tasks_hit_600.append(f"🔥 <a href='{task_link}'>{task_name}</a> <b>({slot_text} slots)</b>")
            
            if new_tasks_found:
                msg_new = f"📢 <b>CÓ {len(new_tasks_found)} TASK MỚI:</b>\n\n" + "\n".join(new_tasks_found)
                msg_new += f"\n\n🔗 <a href='https://hub.axisrobotics.ai/?tab=hub'>Mở Axis Hub</a>"
                send_telegram_message(msg_new)
                
            if tasks_hit_600:
                msg_600 = f"⚠️ <b>HOT: TASK ĐẠT >600 SLOT:</b>\n\n" + "\n".join(tasks_hit_600)
                send_telegram_message(msg_600)
            
            if is_first_run:
                is_first_run = False 
                
        except Exception as e:
            pass
        time.sleep(20)

# ==========================================
# PHẦN 4: KHỞI CHẠY HỆ THỐNG
# ==========================================
if __name__ == "__main__":
    Thread(target=run_server, daemon=True).start()
    Thread(target=check_telegram_commands, daemon=True).start()
    bot_thong_bao_task()
