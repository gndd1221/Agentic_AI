import requests
import sys
import google.generativeai as genai
from langgraph.graph import StateGraph
import re

# === API 金鑰設定 ===
GEMINI_API_KEY = "AIzaSyA2p-lQ4g0_lzPWvfZItGLICROqP3x13Uw"  # 請替換為你的金鑰
NEWSAPI_KEY = "47bd6f57184e4991bd34f52bef81dcc0"
use_model = "gemini-2.0-flash-lite"

genai.configure(api_key=GEMINI_API_KEY)

# === 狀態定義 ===
class AskNewsState(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setdefault("user_input", "")
        self.setdefault("keywords", [])
        self.setdefault("news_articles", [])
        self.setdefault("summary", "")
        self.setdefault("translated_summary", "")
        self.setdefault("intent", "")
        self.setdefault("conversation_history", [])

# === 節點定義 ===

def user_input_node(state: AskNewsState):
    user_input = input("👤 請輸入：")
    state["user_input"] = user_input
    return state

def intent_router_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    prompt = f"""
請判斷使用者輸入的意圖是以下四類之一（僅回傳四個字）：
查新聞、要求摘要、翻譯、閒聊

使用者輸入：
{state["user_input"]}
"""
    response = model.generate_content(prompt)
    intent = response.text.strip().replace("：", "").replace(":", "")
    print(f"🤖 偵測意圖：{intent}")
    state["intent"] = intent
    state["conversation_history"].append(f"User: {state['user_input']} (意圖: {intent})")
    return state

def keyword_extraction_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    prompt = f"""
根據以下輸入，請提取英文關鍵字並以逗號分隔：
{state['user_input']}
"""
    response = model.generate_content(prompt)
    keywords_text = response.text.strip()
    keywords = [re.sub(r'[^\w\s]', '', kw.strip()) for kw in keywords_text.split(",")]
    state["keywords"] = keywords
    print("🔍 關鍵字：", keywords)
    return state

def news_search_node(state: AskNewsState):
    query = " ".join(state["keywords"])
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWSAPI_KEY}&sortBy=popularity"
    response = requests.get(url)
    news_data = response.json()

    if news_data["status"] == "ok":
        state["news_articles"] = news_data["articles"][:3]
        print("📰 找到新聞：")
        for i, article in enumerate(state["news_articles"], 1):
            print(f"{i}. {article['title']}")
    else:
        print("❌ NewsAPI 查詢失敗")
        state["news_articles"] = []

    return state

def summarization_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    articles_text = "\n".join([f"{article['title']}: {article['content'] or ''}" for article in state["news_articles"]])
    if not articles_text.strip():
        state["summary"] = "無法取得新聞內容"
    else:
        response = model.generate_content(f"請摘要以下新聞內容：\n{articles_text}")
        state["summary"] = response.text
        print("🧠 摘要：", state["summary"])
    return state

def translation_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    response = model.generate_content(f"請將以下內容翻譯成繁體中文：\n{state['summary']}")
    state["translated_summary"] = response.text
    print("🌐 翻譯：", state["translated_summary"])
    return state

def chat_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    history = "\n".join(state["conversation_history"])
    prompt = f"""
你是一個友善聊天助手，以下是對話歷史：
{history}

使用者：{state['user_input']}
請回應：
"""
    response = model.generate_content(prompt)
    reply = response.text.strip()
    print("🤖 回應：", reply)
    state["conversation_history"].append(f"AI: {reply}")
    
    # 檢查是否退出
    if state["user_input"].lower() in ["退出", "結束", "bye", "exit"]:
        print("🤖 對話結束")
        sys.exit()  # 結束程式
        return None  # 停止對話
    return state

# === 構建 LangGraph ===
graph = StateGraph(AskNewsState)

graph.add_node("user_input", user_input_node)
graph.add_node("intent_router", intent_router_node)
graph.add_node("keyword_extraction", keyword_extraction_node)
graph.add_node("news_search", news_search_node)
graph.add_node("summarization", summarization_node)
graph.add_node("translation", translation_node)
graph.add_node("chat_node", chat_node)

graph.add_edge("user_input", "intent_router")
graph.add_conditional_edges(
    "intent_router",
    lambda state: state["intent"],
    {
        "查新聞": "keyword_extraction",
        "要求摘要": "summarization",
        "翻譯": "translation",
        "閒聊": "chat_node",
    }
)
graph.add_edge("keyword_extraction", "news_search")
graph.add_edge("news_search", "summarization")
graph.add_edge("summarization", "translation")
graph.add_edge("translation", "chat_node")  # 結尾導回聊天，繼續互動
graph.add_edge("chat_node", "user_input")   # 回到輸入，持續對話

graph.set_entry_point("user_input")
app = graph.compile()

# === 主程式迴圈 ===
if __name__ == "__main__":
    state = AskNewsState()
    while True:
        config = {"recursion_limit": 100}
        state = app.invoke(state, config=config)
        if state is None:
            break