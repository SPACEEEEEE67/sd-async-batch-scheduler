# Stable Diffusion API 雙執行緒自動化批次渲染管線

一個基於 Python `requests` 與 `threading` 模組開發的 AIGC 自動化排程腳本。支援動態模型熱切換、客製化尺寸與張數設定、非同步進度監聽，並針對中低階顯卡實作了 Windows TDR 硬體防禦。

## ✨ 核心功能
* **雙執行緒非同步解耦（Multi-threading）：** 主執行緒發送高壓算圖請求，副執行緒以 2.5 Hz 降頻輪詢進度，防範 CLI 介面凍結與後端伺服器死鎖。
* **串行迭代演算法（VRAM 優化）：** 改寫底層配置改用 `n_iter` 串行排程，在 0% 額外顯存增長下實現連續多張量產。
* **軟體防禦性設計（Robust UX）：** 基於 DRY 原則重構之 `get_valid_int()` 防呆函數，阻斷前端非預期型態輸入。
* **純淨落盤（Loop Decoding）：** 自動遍歷響應體並剔除 WebUI 預設 Grid 拼接圖。

## 🛠️ 開發環境與依賴
* Python 3.8+
* `requests`
* Stable Diffusion WebUI (需拉起 `--api` 參數)

## 🚀 快速開始
1. 確保 Stable Diffusion WebUI 已啟動且開啟 API 模式。
2. 複製本專案：`git clone https://github.com/你的帳號/專案名稱.git`
3. 執行腳本：`python main.py`
