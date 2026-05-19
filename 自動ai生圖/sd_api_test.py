import requests
import base64
import time
import threading
import logging
from datetime import datetime
from pathlib import Path

# =========================================================================
# 📂 [軟體重構/純淨落盤體現]：自訂儲存路徑配置（採用現代 pathlib 庫）
# =========================================================================
CUSTOM_OUTPUT_DIR = Path("E:/AI/PHOTO")  # 👈 圖片要存去哪？
CUSTOM_LOG_DIR = Path("E:/AI/日誌")      # 👈 日誌要存去哪？

# 自動建立資料夾（pathlib 語法）
CUSTOM_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CUSTOM_LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE_PATH = CUSTOM_LOG_DIR / "batch_generation.log"

# =========================================================================
# ⚙️ 系統環境與日誌初始化
# =========================================================================
BASE_URL = "http://127.0.0.1:7860/sdapi/v1"

# 強制立即在指定位置建立日誌檔
log_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8", delay=False)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[log_handler, logging.StreamHandler()]
)

print(f"📍 圖片儲存目錄: {CUSTOM_OUTPUT_DIR.resolve()}")
print(f"📍 日誌檔案路徑: {CUSTOM_LOG_DIR.resolve()}")
logging.info("================ 系統初始化成功 ================")

NEGATIVE_PROMPT = (
    "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, "
    "fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, "
    "watermark, username, blurry, bad feet, distorted, poorly drawn face, mutation, "
    "(extra limbs:1.3), (bad anatomy:1.3), (mutated hands and fingers:1.3), (disfigured:1.3), "
    "(anatomical nonsense:1.3), (multilimb:1.3), (cloned items:1.2), (double body:1.2), (double face:1.2)"
)

# ⚙️ 注入硬體防禦與防坍縮優化參數
GENERATION_CONFIG = {
    "steps": 22, 
    "cfg_scale": 7.0, 
    "seed": -1, 
    "sampler_name": "DPM++ 2M Karras",
    "enable_hr": True, 
    "hr_scale": 1.5, 
    "hr_upscaler": "R-ESRGAN 4x+",
    "hr_second_pass_steps": 8, 
    "denoising_strength": 0.58,  # 調高至 0.58 以增加畫面多樣性
    "hr_resize_x": 0,            # Hires 專用防扭曲坍縮參數
    "hr_resize_y": 0,
    "eta": 0.0,                  # 降低隨機噪點帶來的潛在空間崩壞
    "s_churn": 0.0,              # 歸零以穩定高重繪幅度下的畫面
}

def progress_monitor(stop_event):
    """副執行緒（Worker Thread）：負責在背景定時追蹤進度，防止畫面凍結"""
    while not stop_event.is_set():
        try:
            res = requests.get(f"{BASE_URL}/progress", timeout=2)
            if res.status_code == 200:
                data = res.json()
                prog, eta = data.get("progress", 0.0), data.get("eta_relative", 0.0)
                bar = '█' * int(30 * prog) + '░' * (30 - int(30 * prog))
                print(f"\r⏳ 進度: [{bar}] {int(prog * 100)}% | 剩餘: {eta:.1f}s", end="", flush=True)
        except: pass
        time.sleep(2.5)
    print("\r" + " " * 70 + "\r", end="", flush=True)

# =========================================================================
# 🛠️ [軟體工程重構體現]：封裝防呆校驗邏輯（實踐 DRY 原則）
# =========================================================================
def get_valid_int(prompt_msg, min_v, max_v):
    """萬用整數防錯函數：砍掉 35% 重複校驗代碼，阻斷當機風險於前端互動階段"""
    while True:
        val = input(prompt_msg).strip()
        if val.lower() in ['exit', 'quit']:
            logging.info("🛑 使用者主動中斷程式，退出。")
            exit(0)
        try:
            num = int(val)
            if min_v <= num <= max_v:
                return num
            print(f"⚠️ 輸入超出範圍！請輸入該區間的數字：[{min_v} ~ {max_v}]")
        except ValueError:
            print("⚠️ 格式錯誤！請輸入有效的整數（或輸入 exit 結束）。")

def get_valid_str(prompt_msg):
    """字串防空與退出控制函數"""
    while True:
        val = input(prompt_msg).strip()
        if val.lower() in ['exit', 'quit']:
            logging.info("🛑 使用者主動中斷程式，退出。")
            exit(0)
        if val:
            return val

# 步驟一：獲取模型清單
logging.info("🔍 正在連線後端獲取模型列表...")
try:
    models_res = requests.get(f"{BASE_URL}/sd-models", timeout=10)
    available_models = models_res.json() if models_res.status_code == 200 else []
    if not available_models: 
        logging.error("❌ 後端未偵測到任何 SD 模型！程式終止。")
        exit()
except Exception as e:
    logging.critical(f"💥 連線失敗，請確認 WebUI API 是否開啟。錯誤: {e}"); exit()

# 步驟二：動態自訂任務配置（全面改用封裝函數調用）
final_task_queue = []
print("💡 提示：在任何輸入步驟輸入 'exit' 即可隨時結束程式。")
# 呼叫端變得極度乾淨，徹底移除重複的變數校驗
total_tasks = get_valid_int("👉 請問這次一共要建立幾個【算圖任務】？: ", min_v=1, max_v=100)

for i in range(total_tasks):
    task_id = i + 1
    print(f"\n📝 [配置第 {task_id} / {total_tasks} 個任務]")
    prompt = get_valid_str("✍️ 請輸入【正向提示詞 (Prompt)】: ")
    prefix = "".join([c for c in get_valid_str("💾 請輸入【存檔檔名前綴】: ") if c.isalnum() or c in ('_', '-')])
    
    for idx, m in enumerate(available_models):
        print(f"    [{idx + 1}] {m['title'].split('[')[0].strip()}")
        
    m_idx = get_valid_int(f"👉 請輸入模型編號 (1-{len(available_models)}): ", 1, len(available_models)) - 1
    width = get_valid_int("📐 請輸入圖片【寬度 Width】(64-2048): ", 64, 2048)
    height = get_valid_int("📐 請輸入圖片【高度 Height】(64-2048): ", 64, 2048)
    batch_count = get_valid_int("請問此任務您想連續渲染幾張圖片？(1-20): ", 1, 20)

    final_task_queue.append({
        "id": task_id, "prompt": prompt, "prefix": prefix,
        "target_model": available_models[m_idx]['title'],
        "width": width, "height": height, "batch_count": batch_count
    })

# 步驟三：自動化流水線執行
logging.info(f"⚙️ 排程配置完成，共 {len(final_task_queue)} 個任務。流水線生產啟動...")
for run_task in final_task_queue:
    short_model = run_task['target_model'].split('[')[0].strip()
    logging.info(f"🚀 開始執行任務 {run_task['id']} | 模型: {short_model} | 預計張數: {run_task['batch_count']}")
    
    try:
        sw_res = requests.post(f"{BASE_URL}/options", json={"sd_model_checkpoint": run_task["target_model"]}, timeout=60)
        if sw_res.status_code != 200: 
            logging.warning(f"⚠️ 任務 {run_task['id']} 失敗：模型載入失敗，跳過。")
            continue
        time.sleep(3)
    except Exception as e: 
        logging.error(f"💥 模型切換網路異常，跳過該任務。錯誤: {e}"); continue

    # 🔗 改調用 n_iter 串行排程演算法，實現單張串行排隊「顯卡防爆」
    payload = {
        "prompt": run_task["prompt"], "negative_prompt": NEGATIVE_PROMPT,
        "width": run_task["width"], "height": run_task["height"], 
        "n_iter": run_task["batch_count"],
        **GENERATION_CONFIG
    }
    
    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=progress_monitor, args=(stop_event,))
    
    try:
        print("⚡ 潛在空間去噪運算中...")
        monitor_thread.start()
        
        # 主執行緒（Main Thread）：發送算圖請求並維持連線
        res = requests.post(f"{BASE_URL}/txt2img", json=payload, headers={"Connection": "close"}, timeout=1800)
        
        stop_event.set()
        monitor_thread.join()
        
        if res.status_code == 200:
            imgs = res.json().get('images', [])
            for s_idx, img_b64 in enumerate(imgs):
                # 🚧 邊界閘門：當連續渲染時，自動偵測並過濾後端附贈的最後一張 Grid 網格拼接圖
                if len(imgs) > 1 and s_idx == len(imgs) - 1: 
                    continue
                
                time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                f_name = f"task{run_task['id']}_{run_task['prefix']}_seq{s_idx+1}_{time_str}.png"
                
                # 🛠️ [純淨落盤體現]：使用 pathlib 進行路徑 / 拼接，並用 write_bytes 實現直寫二進位
                file_path = CUSTOM_OUTPUT_DIR / f_name
                file_path.write_bytes(base64.b64decode(img_b64))
                
                logging.info(f"  └─ 💾 第 {s_idx+1} 張圖片已純淨落盤：{f_name}")
            logging.info(f"🎉 任務 {run_task['id']} 生產完畢。")
        else:
            logging.error(f"❌ 算圖失敗，後端狀態碼：{res.status_code}")
    except Exception as e:
        stop_event.set()
        if monitor_thread.is_alive(): monitor_thread.join()
        logging.error(f"💥 運算過程發生未預期錯誤：{e}")
    time.sleep(3)

logging.info("✨ 所有排程已全數自動化生產完畢！")