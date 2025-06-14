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
import logging

# === Custom Logging Filter ===
class NonEmptyFilter(logging.Filter):
    def filter(self, record):
        return record.msg.strip() != ""

# === Logging Configuration ===
log_filename = f"asknews_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.addFilter(NonEmptyFilter())
stream_handler = logging.StreamHandler()
stream_handler.addFilter(NonEmptyFilter())

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[file_handler, stream_handler]
)
logger = logging.getLogger(__name__)


# === API Key Configuration ===
GEMINI_API_KEY = "apikey"
NEWSAPI_KEY = "apikey"
LINE_ACCESS_TOKEN = "LINE_ACCESS_TOKEN"

use_model = "gemini-2.5-flash-preview-04-17"

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
        self.setdefault("translated_summary", "")
        self.setdefault("intent", "")
        self.setdefault("conversation_history", [])
        self.setdefault("refinement_history", [])

# === Node Definitions ===
def user_input_node(state: AskNewsState):
    user_input = input("👤 請輸入最近關心的議題：")
    state["user_input"] = user_input
    state["conversation_history"].append(f"User: {user_input}")
    logger.info(f"User Input: {user_input}")
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
    logger.info(f"Detected Intent: {intent}")
    state["intent"] = intent
    state["conversation_history"].append(f"AI: 偵測到意圖 - {intent}")
    return state

def query_refinement_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    refinement_history = state["refinement_history"]
    user_input = state["user_input"]
    
    if not refinement_history:
        prompt = f"基於使用者的輸入：'{user_input}'，請提出一個簡短問題來幫助澄清或聚焦他們的查詢。"
    else:
        history = "\n".join(refinement_history)
        prompt = f"以下是對話歷史：\n{history}\n\n請基於對話歷史提出下一個簡短問題來進一步澄清使用者的查詢。"

    
    response = model.generate_content(prompt)
    question = response.text.strip()
    refinement_history.append(f"AI: {question}")
    print(f"🤖 {question}")
    logger.info(f"AI Question: {question}")
    
    user_response = input("👤 請回應細節方向或者回答直接搜尋：")
    refinement_history.append(f"User: {user_response}")
    state["conversation_history"].append(f"User: {user_response}")
    logger.info(f"User Response: {user_response}")

    search_intent_keywords = ["直接搜尋", "搜尋", "查詢", "search", "query"]
    if any(kw in user_response.lower() for kw in search_intent_keywords):
        state["refined_query"] = user_response
        print("🤖 偵測到搜尋意圖，準備進行新聞搜尋。")
        logger.info("Search Intent Detected, Preparing News Search")
        return state

    history = "\n".join(refinement_history)
    confirm_prompt = f"""
    以下是對話歷史：
    {history}

    基於使用者的回應：'{user_response}'，請判斷使用者是否準備好進行新聞搜尋，只要用戶的回答足夠進行搜尋即可。
    回答:是/否。
    """

    confirm_response = model.generate_content(confirm_prompt)
    if confirm_response.text.strip().lower() == "是":
        state["refined_query"] = user_response
        print("🤖 查詢已確認，準備進行新聞搜尋。")
        logger.info("Query Confirmed, Preparing News Search")
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

    請基於最終查詢和對話歷史：'{refined_query}'，生成三個以下最相關的關鍵字，以逗號分隔。
    請注意！如果回復有直接查詢的意圖，要忽略對話中系統提供的關鍵字。
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
    logger.info(f"Extracted Keywords: {state['keywords']}")

    prompt = f"""
    以下是使用者與AI的對話歷史：
    {history}
    以及最終查詢：'{refined_query}'，

    請幫我生成英文的新聞搜尋語句，
    例如：Please search for news regarding Trump and Musk discussing the world economic landscape.
    """
    response = model.generate_content(prompt)
    state["refined_query"] = response.text.strip()
    print("簡要英文搜索意圖：", state["refined_query"])
    logger.info(f"簡要英文搜索意圖: {state['refined_query']}\n")
    return state

def news_search_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    keywords = state["keywords"]
    user_input = state["user_input"]
    
    has_chinese = re.search(r'[\u4e00-\u9fff]', user_input)
    language = "en"
    
    query = " OR ".join(keywords)
    
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
            articles = news_data["articles"][:50]
            titles = "\n".join([f"{i+1}. {article['title']}" for i, article in enumerate(articles)])
            title_list = [article['title'] for article in articles]
            query = state["refined_query"]
            prompt = f"以下是新聞標題列表，請判斷每篇新聞是否與查詢 '{query}' 相關，回傳 'Yes' 或 'No'，每行一個回應：\n{titles}"
            response = model.generate_content(prompt)
            logger.info(f"相關性標註: \n")
            answers = response.text.strip().split('\n')
            
            relevant_articles = []
            for i, answer in enumerate(answers):
                logger.info(f"{answer.strip().lower()} {i+1} {title_list[i]}")
                if i < len(articles) and answer.strip().lower() == 'yes':
                    relevant_articles.append(articles[i])
            
            state["news_articles"] = relevant_articles
            if relevant_articles:
                print("📰 找到相關新聞：")
                for i, article in enumerate(relevant_articles, 1):
                    print(f"{i}. {article['title']} - {article['url']}")
                    logger.info(f"Relevant Article {i}: {article['title']} - {article['url']}")
            else:
                print("❌ 無符合意圖的新聞")
                logger.info("No Relevant News Found")
        else:
            print("❌ 無相關新聞")
            logger.info("No News Found")
            state["news_articles"] = []
    except Exception as e:
        print(f"❌ NewsAPI 查詢失敗: {str(e)}")
        logger.error(f"NewsAPI Query Failed: {str(e)}")
        state["news_articles"] = []
    return state

def summary_and_translation_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    articles = state["news_articles"]
    
    if not articles:
        state["translated_summary"] = "無法取得新聞內容"
        print("🌐 匯總短文：\n無法取得新聞內容")
        logger.info("Summary: Unable to retrieve news content")
        #send_line_broadcast(state["translated_summary"])
        return state
    
    articles_text = "\n\n".join([
        f"標題: {article['title']}\n內容: {article['content'] or '無內容'}\n網址: {article['url']}"
        for article in articles
    ])

    prompt = f"""
請為以下多篇新聞生成一篇簡潔的繁體中文分段落的匯總短文（約100-150字），並包含一個醒目的標題。匯總短文應整合所有新聞的核心內容，突出重點，並以流暢的敘述方式呈現（不要使用 markdown 語法）。標題應吸引人且反映新聞主題。輸出格式如下：
[醒目標題]

[匯總短文 段落1]

[匯總短文 段落2]
...
來源網址:
-[標題1] : [網址1]
-[標題2] : [網址2]
...

新聞內容：
{articles_text}
"""
    response = model.generate_content(prompt)
    state["translated_summary"] = response.text.strip()
    print("🌐 翻譯後的摘要：\n", state["translated_summary"])
    logger.info(f"Translated Summary:\n{state['translated_summary']}")
    
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
    logger.info(f"AI Response: {reply}")
    state["conversation_history"].append(f"AI: {reply}")
    
    if state["user_input"].lower() in ["退出", "結束", "bye", "exit", "掰掰", "再見", "滾", "881", "byebye", "bye bye"]:
        print("🤖 對話結束")
        logger.info("Conversation Ended")
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
            logger.info("廣播訊息發送成功！LINE Broadcast Sent Successfully")
            pprint(api_response)
        except Exception as e:
            print("發送失敗：", str(e))
            logger.error(f"發送失敗 LINE Broadcast Failed: {str(e)}")

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
        "要求摘要": "query_refinement",
        "翻譯": "query_refinement",
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
    logger.info("System Started")
    while True:
        config = {"recursion_limit": 100}
        state = app.invoke(state, config=config)
        if state is None:
            logger.info("System Terminated")
            break