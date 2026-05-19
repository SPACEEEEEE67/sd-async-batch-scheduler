import requests

# 查詢模型列表的官方 API 節點
URL = "http://127.0.0.1:7860/sdapi/v1/sd-models"

try:
    response = requests.get(URL)
    if response.status_code == 200:
        models = response.json()
        print("====== 🔍 你的本地模型完整名稱列表 ======")
        for index, model in enumerate(models):
            # title 就是我們待會要用來切換的「唯一識別金鑰」
            print(f"[{index + 1}] {model['title']}")
        print("========================================")
    else:
        print(f"無法取得列表，錯誤碼：{response.status_code}")
except Exception as e:
    print(f"連線失敗：{e}")