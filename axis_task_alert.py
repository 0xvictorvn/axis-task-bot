import time
import requests
from flask import Flask
from threading import Thread

# ==========================================
# PHẦN 1: CẤU HÌNH CƠ BẢN
# ==========================================
TELEGRAM_TOKEN = '8655926285:AAHURVEuQ6WC4EJjybG7Io29ENMN8HQA8M8'
TELEGRAM_CHAT_ID = '1246404230'

seen_task_ids = set()

# Biến để theo dõi tình trạng web
is_website_down = False
failed_attempts = 0
MAX_FAILURES = 3  # Cho phép lag 2 lần, đến lần thứ 3 mới báo sập

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot đang thức và hoạt động 24/7!"

def run_server():
    app.run(host='0.0.0.0', port=8080)

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
        requests.post(url, json=payload)
    except Exception as e:
        print("Lỗi gửi tin nhắn:", e)

# ==========================================
# PHẦN 3: HÀM LẤY DỮ LIỆU (CÓ CHỐNG LAG & BÁO SẬP)
# ==========================================
def get_axis_tasks():
    global is_website_down, failed_attempts

    url = 'https://hub.axisrobotics.ai/api/tasks'
    params = {
        'sort_order': 'desc', 'status': 'active', 'search': '', 'page': '1', 'per_page': '9'
    }
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'vi,en-US;q=0.9,en;q=0.8',
        'referer': 'https://hub.axisrobotics.ai/?tab=hub',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
    }

    try:
        # Đặt timeout 15s để châm chước nếu web hơi chậm
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        # === NẾU WEB SỐNG LẠI SAU KHI SẬP ===
        if is_website_down:
            send_telegram_message("🟢 <b>TIN VUI:</b> Web Axis đã mượt trở lại! Bot đang tiếp tục canh task.")
            is_website_down = False
            
        failed_attempts = 0 # Reset bộ đếm lỗi về 0 vì lấy data thành công
        data = response.json()
        
        if isinstance(data, dict) and 'tasks' in data:
            return data['tasks']
        elif isinstance(data, list):
            return data
        return []
        
    except Exception as e:
        failed_attempts += 1
        print(f"⚠️ Cảnh báo: Lần {failed_attempts}/{MAX_FAILURES} web Axis lag hoặc không phản hồi ({e})")
        
        # === NẾU WEB CHẾT ĐÚNG 3 LẦN LIÊN TIẾP VÀ CHƯA BÁO ===
        if failed_attempts == MAX_FAILURES and not is_website_down:
            send_telegram_message("🔴 <b>CẢNH BÁO:</b> Web Axis đang bị sập hoặc quá tải nặng! Bot sẽ im lặng và báo lại khi web mượt.")
            is_website_down = True
            
        return []

# ==========================================
# PHẦN 4: LOGIC QUÉT VÀ LỌC TASK MỚI (ĐÃ CÓ LINK)
# ==========================================
def bot_thong_bao_task():
    global seen_task_ids
    is_first_run = True 

    print("Bắt đầu khởi chạy vòng lặp check task...")
    
    while True:
        try:
            tasks = get_axis_tasks()
            new_tasks_found = [] 

            for task in tasks:
                task_id = task.get('id') or task.get('_id')
                task_name = task.get('title') or task.get('name') or 'Task không tên'
                
                if not task_id: continue
                
                if task_id not in seen_task_ids:
                    seen_task_ids.add(task_id) 
                    
                    if not is_first_run:
                        task_link = f"https://hub.axisrobotics.ai/action?id={task_id}"
                        new_tasks_found.append(f"🔹 <a href='{task_link}'>{task_name}</a>")
            
            if new_tasks_found:
                formatted_list = "\n".join(new_tasks_found)
                
                msg = f"📢 <b>CÓ {len(new_tasks_found)} TASK MỚI:</b>\n\n"
                msg += formatted_list
                msg += f"\n\n🔗 <a href='https://hub.axisrobotics.ai/?tab=hub'>Mở Axis Hub</a>"
                
                send_telegram_message(msg)
            
            if is_first_run:
                is_first_run = False 
                print(f"Lần chạy đầu: Ghi nhớ {len(seen_task_ids)} task cũ. Bắt đầu rình task mới...")
                
        except Exception as e:
            print("Lỗi vòng lặp:", e)
        
        time.sleep(30)

# ==========================================
# PHẦN 5: KHỞI CHẠY CHƯƠNG TRÌNH
# ==========================================
if __name__ == "__main__":
    t = Thread(target=run_server)
    t.daemon = True 
    t.start()
    
    bot_thong_bao_task()
