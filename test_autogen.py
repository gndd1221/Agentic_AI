import autogen
import requests
import google.generativeai as genai

# === API 金鑰設定 ===
GEMINI_API_KEY = "AIzaSyA2p-lQ4g0_lzPWvfZItGLICROqP3x13Uw"  # 請替換為你的金鑰
NEWSAPI_KEY = "47bd6f57184e4991bd34f52bef81dcc0"
use_model = "gemini-2.0-flash-lite"

# 配置 Generative AI API 金鑰
genai.configure(api_key=GEMINI_API_KEY)

# 配置 AutoGen 的語言模型
llm_config = {
    "model": use_model,
    "api_key": GEMINI_API_KEY,
    "api_type": "google"
}

# 定義代理
user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    system_message="""你代表用戶，負責接收人類輸入並將其傳遞給群聊。
    當 coordinator 要求提供新聞主題時，請在終端機中顯示 '請輸入新聞主題：'，並等待人類輸入。
    將用戶輸入的主題傳回群聊。""",
    human_input_mode="ALWAYS",  # 始終要求人類輸入
    code_execution_config={"use_docker": False}
)

coordinator = autogen.AssistantAgent(
    name="coordinator",
    system_message="""你是一個新聞查詢系統的協調者，負責管理流程。你的任務是：
    1. 向 user_proxy 發送消息，要求提供新聞主題，例如：'請提供一個新聞主題。'
    2. 等待 user_proxy 回傳新聞主題。
    3. 將新聞主題傳給 keyword_extractor 提取關鍵字。
    4. 如果關鍵字少於 2 個，向 user_proxy 要求更多信息。
    5. 將關鍵字傳給 news_searcher 搜索新聞。
    6. 如果新聞少於 3 篇，詢問 user_proxy 是否調整關鍵字。
    7. 將新聞傳給 summarizer 進行摘要。
    8. 將摘要傳給 translator 翻譯成中文。
    9. 將結果傳回給 user_proxy。
    請確保在發送請求後等待回應，保持對話流程順暢。""",
    llm_config=llm_config
)

keyword_extractor = autogen.AssistantAgent(
    name="keyword_extractor",
    system_message="""你的任務是從給定的文本中提取關鍵字並將其翻譯成英文，返回逗號分隔的列表（例如：keyword1, keyword2, keyword3）。
    如果收到 coordinator 的指令，請處理指定的文本並返回結果。""",
    llm_config=llm_config
)

news_searcher = autogen.AssistantAgent(
    name="news_searcher",
    system_message="""你的任務是使用給定的關鍵字從 NewsAPI 搜索新聞，並返回最多 5 篇新聞文章的標題和內容。
    使用以下 API: https://newsapi.org/v2/everything?q={query}&apiKey={NEWSAPI_KEY}&sortBy=popularity
    如果收到 coordinator 的指令，請執行搜索並返回結果。如果搜索失敗，返回錯誤信息。""",
    llm_config=llm_config
)

summarizer = autogen.AssistantAgent(
    name="summarizer",
    system_message="""你的任務是對給定的新聞文章進行摘要，返回簡潔的總結。
    如果收到 coordinator 的指令，請處理指定的新聞內容並返回摘要。""",
    llm_config=llm_config
)

translator = autogen.AssistantAgent(
    name="translator",
    system_message="""你的任務是將給定的文本翻譯成繁體中文。
    如果收到 coordinator 的指令，請處理指定的文本並返回翻譯結果。""",
    llm_config=llm_config
)

# 定義群聊
groupchat = autogen.GroupChat(
    agents=[user_proxy, coordinator, keyword_extractor, news_searcher, summarizer, translator],
    messages=[],
    max_round=20  # 限制對話輪次，避免無限循環
)

# 創建群聊管理器
manager = autogen.GroupChatManager(
    groupchat=groupchat,
    llm_config=llm_config
)

# 主函數
def main():
    # 通過 user_proxy 啟動對話
    user_proxy.initiate_chat(
        manager,
        message="請開始新聞查詢流程。"
    )

if __name__ == "__main__":
    main()