import requests
import google.generativeai as genai
from langgraph.graph import Graph, StateGraph
import re  # 用於清理關鍵字

# 直接設置 API 金鑰（請替換為你的實際金鑰）
GEMINI_API_KEY = "api"  # 替換為你的 Gemini API 金鑰
NEWSAPI_KEY = "api"        # 替換為你的 NewsAPI 金鑰
use_model = "gemini-2.5-flash-preview-04-17"  # 使用的模型名稱

# 配置 Generative AI API 金鑰
genai.configure(api_key=GEMINI_API_KEY)

# 定義狀態類
class AskNewsState(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setdefault("user_input", "")
        self.setdefault("keywords", [])
        self.setdefault("news_articles", [])
        self.setdefault("summary", "")
        self.setdefault("translated_summary", "")

# 節點定義
def user_input_node(state: AskNewsState):
    # 模擬用戶輸入，實際應用中應由 UI 提供
    state["user_input"] = "我想了解最近的ESG碳排新聞"
    return state

def keyword_extraction_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    # 改進提示詞，要求返回逗號分隔的關鍵字
    prompt = f"Extract keywords from the following text and translate the keywords to englist return them as a comma-separated list (e.g., keyword1, keyword2, keyword3): {state['user_input']}"
    response = model.generate_content(prompt)
    print("Raw response from Gemini API:", response.text)
    
    # 使用正則表達式提取關鍵字（假設回應是逗號分隔的文字）
    keywords_text = response.text.strip()
    keywords = [kw.strip() for kw in keywords_text.split(",")]
    # 進一步清理，移除可能的格式符號
    keywords = [re.sub(r'[^\w\s]', '', kw) for kw in keywords]
    state["keywords"] = keywords
    print("Cleaned keywords:", state["keywords"])
    return state

def news_search_node(state: AskNewsState):
    query = " ".join(state["keywords"])
    print("Search query:", query)
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWSAPI_KEY}&sortBy=popularity"
    response = requests.get(url)
    news_data = response.json()

    if news_data["status"] == "ok":
        state["news_articles"] = news_data["articles"][:5]  # 取前 5 篇新聞
        print("Found articles:", [article["title"] for article in state["news_articles"]])
    else:
        print("NewsAPI error:", news_data.get("message", "Unknown error"))
        state["news_articles"] = []

    return state

def summarization_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    articles_text = "\n".join([f"{article['title']}: {article['content'] or ''}" for article in state["news_articles"]])

    if not articles_text.strip():
        state["summary"] = "無法獲取新聞文章內容。"
    else:
        response = model.generate_content(f"Summarize the following news articles: {articles_text}")
        state["summary"] = response.text
    # print("Summary:", state["summary"])
    return state

def translation_node(state: AskNewsState):
    model = genai.GenerativeModel(use_model)
    response = model.generate_content(f"Translate the following text to Chinese(繁體中文): {state['summary']}")
    state["translated_summary"] = response.text
    return state

def print_summary_node(state: AskNewsState):
    print("Translated summary:", state["translated_summary"])
    return state

# 構建 StateGraph
graph = StateGraph(AskNewsState)

# 添加節點
graph.add_node("user_input", user_input_node)
graph.add_node("keyword_extraction", keyword_extraction_node)
graph.add_node("news_search", news_search_node)
graph.add_node("summarization", summarization_node)
graph.add_node("translation", translation_node)
graph.add_node("print_summary", print_summary_node)

# 添加邊
graph.add_edge("user_input", "keyword_extraction")
graph.add_edge("keyword_extraction", "news_search")
graph.add_edge("news_search", "summarization")
graph.add_edge("summarization", "translation")
graph.add_edge("translation", "print_summary")

# 設置入口點
graph.set_entry_point("user_input")

# 編譯圖
app = graph.compile()

# 運行
if __name__ == "__main__":
    initial_state = AskNewsState()
    app.invoke(initial_state)