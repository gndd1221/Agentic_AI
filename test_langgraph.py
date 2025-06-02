import requests
import sys
import google.generativeai as genai
from langgraph.graph import StateGraph
import re
import spacy
from datetime import datetime, timedelta

# === API Key Configuration ===
GEMINI_API_KEY = "api_key"  # Replace with your key
NEWSAPI_KEY = "api_key"  # Replace with your key
use_model = "gemini-2.0-flash-lite"

genai.configure(api_key=GEMINI_API_KEY)

# === Load spaCy Chinese Model ===
nlp = spacy.load("zh_core_web_sm")

# === State Definition ===
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

# === Node Definitions ===

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
    user_input = state["user_input"]
    
    # Use Gemini API to extract keywords
    prompt = f"請從以下使用者輸入中擷取關鍵字（以逗號分隔）：\n{user_input}"
    response = model.generate_content(prompt)
    keywords = response.text.strip().split(',')
    keywords = [kw.strip() for kw in keywords if kw.strip()]
    
    # Translate keywords to English if necessary
    translated_keywords = []
    for kw in keywords:
        if re.search(r'[\u4e00-\u9fff]', kw):  # Check if keyword contains Chinese characters
            translate_prompt = f"Translate the following Chinese keyword to English, only output the English: {kw}"
            translate_response = model.generate_content(translate_prompt)
            translated_kw = translate_response.text.strip()
            translated_keywords.append(translated_kw)
        else:
            translated_keywords.append(kw)

    # Filter out news-related keywords
    filter_list = ["news", "新聞", "new", "最新", "recent", "today", "yesterday", "昨天"]
    filtered_keywords = [kw for kw in translated_keywords if kw.lower() not in filter_list]
    
    state["keywords"] = filtered_keywords if filtered_keywords else ["general"]
    print("🔍 關鍵字：", state["keywords"])
    return state

def news_search_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    keywords = state["keywords"]
    user_input = state["user_input"]
    
    # Determine language
    has_chinese = re.search(r'[\u4e00-\u9fff]', user_input)
    language = "en"
    
    # Build query
    query = " ".join(keywords)
    
    # Check for time-related keywords
    time_keywords = ["最新", "recent", "today", "yesterday"]
    sort_by = "relevancy"
    from_date = None
    to_date = None
    if any(kw in user_input.lower() for kw in time_keywords):
        sort_by = "publishedAt"
        to_date = datetime.now().strftime("%Y-%m-%d")
        if "yesterday" in user_input.lower() or "昨天" in user_input:
            from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            from_date = to_date
    
    params = {
        "q": query,
        "apiKey": NEWSAPI_KEY,
        "sortBy": sort_by,
        "language": language,
    }
    if from_date and to_date:
        params["from"] = from_date
        params["to"] = to_date
    
    # # Adjust for Taiwan-specific news
    # if "台灣" in user_input or "Taiwan" in user_input.lower():
    #     params["country"] = "tw"
    
    try:
        url = "https://newsapi.org/v2/everything"
        response = requests.get(url, params=params)
        news_data = response.json()
        
        if news_data["status"] == "ok" and news_data["totalResults"] > 0:
            state["news_articles"] = news_data["articles"][:10]  # Top 5 articles
            print("📰 找到新聞：")
            for i, article in enumerate(state["news_articles"], 1):
                print(f"{i}. {article['title']}")
        else:
            print("❌ 無相關新聞")
            state["news_articles"] = []
    except Exception as e:
        print(f"❌ NewsAPI 查詢失敗: {str(e)}")
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
    response = model.generate_content(f"將以下內容翻譯成繁體中文：\n{state['summary']}")
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
    
    if state["user_input"].lower() in ["退出", "結束", "bye", "exit"]:
        print("🤖 對話結束")
        sys.exit()
    return state

# === Build LangGraph ===
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
graph.add_edge("translation", "chat_node")
graph.add_edge("chat_node", "user_input")

graph.set_entry_point("user_input")
app = graph.compile()

# === Main Loop ===
if __name__ == "__main__":
    state = AskNewsState()
    while True:
        config = {"recursion_limit": 100}
        state = app.invoke(state, config=config)
        if state is None:
            break
