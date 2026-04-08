import time
import requests
import os
from flask import Flask
from threading import Thread

# ==========================================
# PHẦN 1: CẤU HÌNH CƠ BẢN (TỐI ƯU HUGGING FACE)
# ==========================================
# Lấy Secret từ Hugging Face. Nhớ cài trong Settings -> Variables and secrets
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8655926285:AAHURVEuQ6WC4EJjybG7Io29ENMN8HQA8M8')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '1246404230')

# Trí nhớ của bot
seen_task_ids = set()           # Nhớ task mới
notified_600_tasks = set()      # Nhớ task đã đạt 600 slot

# Biến theo dõi tình trạng mạng
is_website_down = False
failed_attempts = 0
MAX_FAILURES = 3  # Cho phép lỗi 2 nhịp (40s), nhịp thứ 3 mới báo sập

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot đang thức và hoạt động 24/7 trên Hugging Face!"

def run_server():
    # Hugging Face yêu cầu bắt buộc chạy cổng 7860
    app.run(host='0.0.0.0', port=7860)

# ==========================================
# PHẦN 2: HÀM GỬI TIN NHẮN TELEGRAM
# ==========================================
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True 
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Lỗi gửi tin nhắn:", e)

# ==========================================
# PHẦN 3: LẮNG NGHE LỆNH TỪ TELEGRAM (/status)
# ==========================================
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
                                uptime_msg = "✅ <b>BÁO CÁO:</b> Bot vẫn đang chạy cực khỏe!\n"
                                uptime_msg += f"📡 Trạng thái Axis: {'🔴 Đang sập/Lag' if is_website_down else '🟢 Mượt mà'}"
                                send_telegram_message(uptime_msg)
        except:
            pass
        time.sleep(2)

# ==========================================
# PHẦN 4: HÀM LẤY DỮ LIỆU TỪ AXIS (CÓ CHỐNG SẬP)
# ==========================================
def get_axis_tasks():
    global is_website_down, failed_attempts

    url = 'https://hub.axisrobotics.ai/api/tasks'
    params = {'sort_order': 'desc', 'status': 'active', 'search': '', 'page': '1', 'per_page': '9'}
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'vi,en-US;q=0.9,en;q=0.8',
        'referer': 'https://hub.axisrobotics.ai/?tab=hub',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        if is_website_down:
            send_telegram_message("🟢 <b>TIN VUI:</b> Web Axis đã mượt trở lại! Bot đang tiếp tục canh task.")
            is_website_down = False
            
        failed_attempts = 0 
        data = response.json()
        
        if isinstance(data, dict) and 'tasks' in data:
            return data['tasks']
        elif isinstance(data, list):
            return data
        return []
        
    except Exception as e:
        failed_attempts += 1
        print(f"⚠️ Cảnh báo: Lần {failed_attempts}/{MAX_FAILURES} web Axis lag ({e})")
        
        if failed_attempts == MAX_FAILURES and not is_website_down:
            send_telegram_message("🔴 <b>CẢNH BÁO:</b> Web Axis đang bị sập hoặc quá tải nặng! Bot sẽ im lặng và báo lại khi web mượt.")
            is_website_down = True
            
        return []

# ==========================================
# PHẦN 5: LOGIC QUÉT TASK MỚI & SLOT (20s/lần)
# ==========================================
def bot_thong_bao_task():
    global seen_task_ids, notified_600_tasks
    is_first_run = True 

    print("Bắt đầu khởi chạy vòng lặp check task (20s/lần)...")
    send_telegram_message("🚀 <b>BOT ĐÃ ON:</b> Hệ thống đã khởi động trên Hugging Face. Tốc độ: 20s/quét.")
    
    while True:
        try:
            tasks = get_axis_tasks()
            new_tasks_found = [] 
            tasks_hit_600 = []

            for task in tasks:
                task_id = task.get('id') or task.get('_id')
                task_name = task.get('title') or task.get('name') or 'Task không tên'
                slot_completed = task.get('slot_completed', 0) # Lấy số người hoàn thành, nếu không có mặc định là 0
                
                if not task_id: continue
                
                task_link = f"https://hub.axisrobotics.ai/action?id={task_id}"
                
                # 1. KIỂM TRA TASK MỚI
                if task_id not in seen_task_ids:
                    seen_task_ids.add(task_id) 
                    if not is_first_run:
                        new_tasks_found.append(f"🔹 <a href='{task_link}'>{task_name}</a>")
                        
                # 2. KIỂM TRA TASK ĐẠT 600 SLOT
                if slot_completed >= 600 and task_id not in notified_600_tasks:
                    notified_600_tasks.add(task_id)
                    if not is_first_run:
                        tasks_hit_600.append(f"🔥 <a href='{task_link}'>{task_name}</a> <b>({slot_completed} slots)</b>")
            
            # GỬI TIN NHẮN TASK MỚI
            if new_tasks_found:
                msg_new = f"📢 <b>CÓ {len(new_tasks_found)} TASK MỚI:</b>\n\n"
                msg_new += "\n".join(new_tasks_found)
                msg_new += f"\n\n🔗 <a href='https://hub.axisrobotics.ai/?tab=hub'>Mở Axis Hub</a>"
                send_telegram_message(msg_new)
                
            # GỬI TIN NHẮN BÁO ĐỘNG ĐẠT 600 SLOT
            if tasks_hit_600:
                msg_600 = f"⚠️ <b>HOT: TASK ĐÃ ĐẠT HƠN 600 SLOT:</b>\n\n"
                msg_600 += "\n".join(tasks_hit_600)
                send_telegram_message(msg_600)
            
            if is_first_run:
                is_first_run = False 
                print(f"Lần chạy đầu: Nhớ {len(seen_task_ids)} task cũ và {len(notified_600_tasks)} task >600 slot.")
                
        except Exception as e:
            print("Lỗi vòng lặp chính:", e)
        
        # Đã giảm xuống 20 giây theo yêu cầu
        time.sleep(20)

# ==========================================
# PHẦN 6: KHỞI CHẠY ĐA LUỒNG
# ==========================================
if __name__ == "__main__":
    t1 = Thread(target=run_server)
    t1.daemon = True 
    t1.start()
    
    t2 = Thread(target=check_telegram_commands)
    t2.daemon = True
    t2.start()
    
    bot_thong_bao_task()
