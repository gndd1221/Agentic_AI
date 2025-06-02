import os
import uuid
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models.broadcast_request import BroadcastRequest
from linebot.v3.messaging.models.text_message import TextMessage
from pprint import pprint

# 配置 LINE Channel Access Token（請替換為您的實際 token）
#LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN", "YOUR_CHANNEL_ACCESS_TOKEN")
LINE_ACCESS_TOKEN = "/ePl9N6VcYH6jUfU4v8VSl+fvRzeTqvGSA/jdVehtE47gyEct/8VKRQ327bjFLbCpuTLsM4azBlzkGbkHdC/h7e6pGTXKBOwboGPm6cEfKYNGF5QUQE8ClvqLkA/Pi5sSBcglgm3+AYReH7BPzNbHwdB04t89/1O/w1cDnyilFU="
# 配置 LINE API
configuration = Configuration(
    host="https://api.line.me",
    access_token=LINE_ACCESS_TOKEN
)

# 主流程
def send_line_broadcast():
    with ApiClient(configuration) as api_client:
        # 創建 Messaging API 實例
        api_instance = MessagingApi(api_client)
        
        # 定義廣播訊息內容
        message = TextMessage(text="能看到嗎 看到私訊我一下")
        
        # 創建廣播請求
        broadcast_request = BroadcastRequest(messages=[message])
        
        # 生成唯一的 retry key
        x_line_retry_key = str(uuid.uuid4())
        
        try:
            # 發送廣播訊息
            api_response = api_instance.broadcast(broadcast_request, x_line_retry_key=x_line_retry_key)
            print("廣播訊息發送成功！回應：")
            pprint(api_response)
        except Exception as e:
            print("發送失敗：", str(e))

if __name__ == "__main__":
    send_line_broadcast()