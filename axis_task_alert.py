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
# PHẦN 3: HÀM LẤY DỮ LIỆU TỪ AXIS
# ==========================================
def get_axis_tasks():
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
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, dict) and 'tasks' in data:
            return data['tasks']
        elif isinstance(data, list):
            return data
        return []
    except Exception as e:
        print("Lỗi lấy dữ liệu Axis:", e)
        return []

# ==========================================
# PHẦN 4: LOGIC QUÉT VÀ LỌC TASK MỚI (ĐÃ CÓ LINK TRỰC TIẾP)
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
                        # TẠO LINK TRỰC TIẾP CHO TASK
                        task_link = f"https://hub.axisrobotics.ai/action?id={task_id}"
                        # Gắn link vào tên task bằng thẻ <a> của HTML
                        new_tasks_found.append(f"🔹 <a href='{task_link}'>{task_name}</a>")
            
            if new_tasks_found:
                formatted_list = "\n".join(new_tasks_found)
                
                msg = f"📢 <b>CÓ {len(new_tasks_found)} TASK MỚI:</b>\n\n"
                msg += formatted_list # Danh sách tên task giờ đã có thể bấm được
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
    # 1. Bật web giả cho Render chạy nền
    t = Thread(target=run_server)
    t.daemon = True 
    t.start()
    
    # 2. Bật não của bot
    bot_thong_bao_task()
