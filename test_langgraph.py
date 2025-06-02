import requests
import sys
import google.generativeai as genai
from langgraph.graph import StateGraph
import re
import spacy
from datetime import datetime, timedelta
import os
import uuid
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models.broadcast_request import BroadcastRequest
from linebot.v3.messaging.models.text_message import TextMessage
from pprint import pprint

# === API Key Configuration ===
<<<<<<< HEAD
GEMINI_API_KEY = "AIzaSyA2p-lQ4g0_lzPWvfZItGLICROqP3x13Uw"  # Replace with your key
NEWSAPI_KEY = "47bd6f57184e4991bd34f52bef81dcc0"        # Replace with your key
LINE_ACCESS_TOKEN = "/ePl9N6VcYH6jUfU4v8VSl+fvRzeTqvGSA/jdVehtE47gyEct/8VKRQ327bjFLbCpuTLsM4azBlzkGbkHdC/h7e6pGTXKBOwboGPm6cEfKYNGF5QUQE8ClvqLkA/Pi5sSBcglgm3+AYReH7BPzNbHwdB04t89/1O/w1cDnyilFU="  # Replace with your Line Channel Access Token
use_model = "gemini-2.5-flash-preview-04-17"  # Free-tier supported model
=======
GEMINI_API_KEY = "api_key"  # Replace with your key
NEWSAPI_KEY = "api_key"  # Replace with your key
use_model = "gemini-2.0-flash-lite"
>>>>>>> 522d4bd8ae4c7f051378b7b2fcd6ea3c6743ea42

genai.configure(api_key=GEMINI_API_KEY)

# === Load spaCy Chinese Model ===
nlp = spacy.load("zh_core_web_sm")

# === State Definition ===
class AskNewsState(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setdefault("user_input", "")
        self.setdefault("refined_query", "")
        self.setdefault("keywords", [])
        self.setdefault("news_articles", [])
        self.setdefault("translated_summary", "")  # Stores final translated summary in Traditional Chinese
        self.setdefault("intent", "")
        self.setdefault("conversation_history", [])
        self.setdefault("refinement_history", [])

# === Node Definitions ===
def user_input_node(state: AskNewsState):
    user_input = input("👤 請輸入：")
    state["user_input"] = user_input
    state["conversation_history"].append(f"User: {user_input}")
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
    intent = response.text.strip().replace(":", "")
    print(f"🤖 偵測意圖：{intent}")
    state["intent"] = intent
    state["conversation_history"].append(f"AI: 偵測到意圖 - {intent}")
    return state

def query_refinement_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    refinement_history = state["refinement_history"]
    user_input = state["user_input"]
    
    if not refinement_history:
        prompt = f"基於使用者的輸入：'{user_input}'，請提出一個簡短問題來幫助澄清或聚焦他們的查詢。"
        response = model.generate_content(prompt)
        question = response.text.strip()
        refinement_history.append(f"AI: {question}")
        print(f"🤖 {question}")
    else:
        history = "\n".join(refinement_history)
        prompt = f"以下是對話歷史：\n{history}\n\n請基於對話歷史提出下一個簡短問題來進一步澄清使用者的查詢。"
        response = model.generate_content(prompt)
        question = response.text.strip()
        refinement_history.append(f"AI: {question}")
        print(f"🤖 {question}")
    
    user_response = input("👤 請回應：")
    refinement_history.append(f"User: {user_response}")
    state["conversation_history"].append(f"User: {user_response}")
    
    confirm_prompt = f"基於使用者的回應：'{user_response}'，請判斷使用者是否準備好進行新聞搜尋（是/否）。"
    confirm_response = model.generate_content(confirm_prompt)
    if confirm_response.text.strip().lower() == "是":
        state["refined_query"] = user_response
        print("🤖 查詢已確認，準備進行新聞搜尋。")
    else:
        state = query_refinement_node(state)
    
    return state

def keyword_extraction_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    refinement_history = state["refinement_history"]
    refined_query = state["refined_query"] or state["user_input"]
    
    history = "\n".join(refinement_history)
    prompt = f"""
以下是使用者與AI的對話歷史：
{history}

請基於對話歷史和最終查詢：'{refined_query}'，擷取重點關鍵字（例如地點、主題、時間等），以逗號分隔。
"""
    response = model.generate_content(prompt)
    keywords = response.text.strip().split(',')
    keywords = [kw.strip() for kw in keywords if kw.strip()]
    
    translated_keywords = []
    for kw in keywords:
        if re.search(r'[\u4e00-\u9fff]', kw):
            translate_prompt = f"Translate the following Chinese keyword to English, only output the English: {kw}"
            translate_response = model.generate_content(translate_prompt)
            translated_kw = translate_response.text.strip()
            translated_keywords.append(translated_kw)
        else:
            translated_keywords.append(kw)

    filter_list = ["news", "新聞", "new", "case", "事件"]
    filtered_keywords = [kw for kw in translated_keywords if kw.lower() not in filter_list]
    
    state["keywords"] = filtered_keywords if filtered_keywords else ["general"]
    print("🔍 關鍵字：", state["keywords"])
    return state

def news_search_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    keywords = state["keywords"]
    user_input = state["user_input"]
    
    has_chinese = re.search(r'[\u4e00-\u9fff]', user_input)
    language = "en"
    
    query = " AND ".join(keywords)
    
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
    
    try:
        url = "https://newsapi.org/v2/everything"
        response = requests.get(url, params=params)
        news_data = response.json()
        
        if news_data["status"] == "ok" and news_data["totalResults"] > 0:
            articles = news_data["articles"][:15]
            titles = "\n".join([f"{i+1}. {article['title']}" for i, article in enumerate(articles)])
            prompt = f"以下是新聞標題列表，請判斷每篇新聞是否與查詢 '{query}' 相關，回傳 'Yes' 或 'No'，每行一個回應：\n{titles}"
            response = model.generate_content(prompt)
            answers = response.text.strip().split('\n')
            
            relevant_articles = []
            for i, answer in enumerate(answers):
                if i < len(articles) and answer.strip().lower() == 'yes':
                    relevant_articles.append(articles[i])
            
            state["news_articles"] = relevant_articles
            if relevant_articles:
                print("📰 找到相關新聞：")
                for i, article in enumerate(relevant_articles, 1):
                    print(f"{i}. {article['title']} - {article['url']}")
            else:
                print("❌ 無符合意圖的新聞")
        else:
            print("❌ 無相關新聞")
            state["news_articles"] = []
    except Exception as e:
        print(f"❌ NewsAPI 查詢失敗: {str(e)}")
        state["news_articles"] = []
    return state

def summary_and_translation_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    articles = state["news_articles"]
    
    if not articles:
        state["translated_summary"] = "無法取得新聞內容"
        print("🌐 摘要並進行翻譯：\n無法取得新聞內容")
        send_line_broadcast(state["translated_summary"])
        return state
    
    articles_text = "\n\n".join([
        f"標題: {article['title']}\n內容: {article['content'] or '無內容'}\n網址: {article['url']}"
        for article in articles
    ])
    
    prompt = f"""
請為以下多篇新聞生成摘要，並直接輸出繁體中文。每篇新聞的摘要應包含標題、簡短內容摘要和網址（不要使用 markdown 語法）。格式如下：
1. 標題: [標題]
   摘要: [內容摘要]
   網址: [網址]

新聞內容：
{articles_text}
"""
    response = model.generate_content(prompt)
    state["translated_summary"] = response.text.strip()
    print("🌐 翻譯後的摘要：\n", state["translated_summary"])
    
    # Send to Line
    send_line_broadcast(state["translated_summary"])
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
    
    if state["user_input"].lower() in ["退出", "結束", "bye", "exit", "掰掰", "再見", "滾", "881"]:
        print("🤖 對話結束")
        sys.exit()
    return state

# === Line Broadcast Function ===
def send_line_broadcast(message_text):
    configuration = Configuration(
        host="https://api.line.me",
        access_token=LINE_ACCESS_TOKEN
    )
    with ApiClient(configuration) as api_client:
        api_instance = MessagingApi(api_client)
        message = TextMessage(text=message_text)
        broadcast_request = BroadcastRequest(messages=[message])
        x_line_retry_key = str(uuid.uuid4())
        try:
            api_response = api_instance.broadcast(broadcast_request, x_line_retry_key=x_line_retry_key)
            print("廣播訊息發送成功！回應：")
            pprint(api_response)
        except Exception as e:
            print("發送失敗：", str(e))

# === Build LangGraph ===
graph = StateGraph(AskNewsState)

graph.add_node("user_input", user_input_node)
graph.add_node("intent_router", intent_router_node)
graph.add_node("query_refinement", query_refinement_node)
graph.add_node("keyword_extraction", keyword_extraction_node)
graph.add_node("news_search", news_search_node)
graph.add_node("summary_and_translation", summary_and_translation_node)
graph.add_node("chat_node", chat_node)

graph.add_edge("user_input", "intent_router")
graph.add_conditional_edges(
    "intent_router",
    lambda state: state["intent"],
    {
        "查新聞": "query_refinement",
        "要求摘要": "summary_and_translation",
        "翻譯": "summary_and_translation",
        "閒聊": "chat_node",
    }
)
graph.add_edge("query_refinement", "keyword_extraction")
graph.add_edge("keyword_extraction", "news_search")
graph.add_edge("news_search", "summary_and_translation")
graph.add_edge("summary_and_translation", "chat_node")
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
