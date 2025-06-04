# AskNews

## 簡介

AskNews 是一個使用 NewsAPI 和 Gemini API 來獲取新聞文章並將其摘要翻譯成中文的項目。該項目使用 Python 編寫，並利用 LangGraph 來管理狀態和流程。它的主要功能包括從用戶輸入中提取關鍵字、搜索相關新聞、生成摘要並將其翻譯成中文。

以新增

1.詢問使用者意圖、聚焦搜尋範圍

2.連接line bot

### 需要更改部分
1. 新增UI介面

## 技術棧

- **NewsAPI**：用於獲取新聞文章。
- **Gemini API**：用於提取關鍵字、生成摘要和翻譯。
- **LangGraph**：用於管理狀態和流程。
- **Python**：編程語言。

## 安裝

1. 安裝所需的 Python 庫：

   ```bash
   conda env create -f environment.yml
   ```

2. 確保你擁有 NewsAPI 和 Gemini API 的金鑰。

## 配置

1. 將你的 API 金鑰替換到程式碼中的相應位置：

   ```python
   GEMINI_API_KEY = "your_gemini_api_key"  # 替換為你的 Gemini API 金鑰
   NEWSAPI_KEY = "your_newsapi_key"        # 替換為你的 NewsAPI 金鑰
   ```

2. 確認使用的 Gemini 模型名稱：

   ```python
   use_model = "gemini-2.5-flash-preview-04-17"  # 使用的模型名稱
   ```

## 使用

1. 運行程式：

   ```bash
   python test.py
   ```

2. 在Terminal輸入想查詢的新聞主題
3. agent會根據新聞主題搜尋相關新聞
4. 將所有查到的新聞都一起彙整，產生摘要
## 注意事項

- 確保你的 API 金鑰有效且未過期。
- 確認 Gemini 模型名稱是否正確且可用。


## 作者

- \[你的名字\]

## 許可

- \[你的許可協議\]
