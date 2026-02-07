import os
import datetime
import pytz
import yfinance as yf
import google.generativeai as genai
import requests

# --- [환경변수 및 설정] ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "")
SEOUL_TZ = pytz.timezone('Asia/Seoul')

# [디스클레이머: 작은 글씨로 하단에 부착될 문구]
DISCLAIMER_TEXT = """
<br>
<hr>
<p style="font-size: 0.8em; color: #999; line-height: 1.4;">
<strong>[안내 및 면책 조항]</strong><br>
본 콘텐츠는 인공지능(AI) 모델을 활용하여 시장 데이터를 기반으로 자동 생성되었습니다.<br>
특정 종목에 대한 투자 권유가 아니며, 데이터의 지연이나 오류가 발생할 수 있습니다.<br>
투자에 대한 모든 책임은 투자자 본인에게 있습니다.<br>
내용에 오류가 있거나 저작권 문제가 발생할 경우, 관리자에게 문의하시면 즉시 삭제 또는 수정 조치하겠습니다.
</p>
"""

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_market_data():
    """데이터 수집 로직 (기존과 동일하되 안정성 강화)"""
    tickers = {"^DJI": "다우존스", "^GSPC": "S&P500", "^IXIC": "나스닥", "^VIX": "공포지수"}
    data_str = "Recent Market Data (7 Days):\n"
    for symbol, name in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="7d")
            if not hist.empty and len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change = ((close - prev) / prev) * 100
                data_str += f"- {name}: {close:.2f} ({change:+.2f}%)\n"
        except: continue
    return data_str

def generate_blog_post(market_data):
    if not GEMINI_API_KEY: return "Error: API Key missing."

    models = ['gemini-2.5-flash', 'Gemini 3 Flash', 'Gemini 2.5 Flash Lite']
    model = None
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            model.generate_content("test", generation_config={"max_output_tokens": 1})
            break
        except: continue
    if not model: return "Error: No available models."

    now = datetime.datetime.now(SEOUL_TZ)

    # [프롬프트 2.0: 전문가 페르소나 및 콘텐츠 강화]
    prompt = f"""
    [Role & Persona]
    You are a professional economic analyst and content creator for 'TheRichWay', a blog specializing in investment and financial technology. Your tone is insightful, data-driven, and slightly provocative to capture reader interest, but always grounded in facts. You write for a sophisticated audience that appreciates deep analysis.

    [Context]
    - Today's Date: {now.strftime('%Y-%m-%d')}
    - Raw Market Data: {market_data}
    - Core Topic: {FOCUS_TOPIC if FOCUS_TOPIC else 'U.S. Market Analysis'}

    [Content Generation Rules]
    1.  **Title Generation**: Create a compelling, slightly sensational title based on the market analysis. The title must be unique and reflect the core message of the article. DO NOT use generic phrases.
    2.  **Deep Analysis (2x-10x More Content)**:
        *   Go beyond a simple summary. Provide a multi-faceted analysis covering:
            *   **Macro-Economic Overview**: Connect market movements to broader economic indicators (e.g., inflation, employment data, Fed policy).
            *   **Sector Spotlight**: Identify and analyze the best and worst-performing sectors.
            *   **Key Market Movers**: Discuss specific stocks or events that significantly impacted the market.
            *   **Investor Sentiment**: Analyze the VIX (fear index) and other sentiment indicators.
            *   **Future Outlook & Strategy**: Offer actionable insights and potential strategies for investors.
    3.  **News Integration**: Assume you have analyzed 10+ reputable financial news sources (e.g., Bloomberg, Reuters, WSJ). Synthesize their key insights into your analysis.
    4.  **Rich Visuals**:
        *   **Tables**: Use Markdown tables extensively to present data clearly.
        *   **Charts**: Integrate at least one or two Mermaid.js charts (e.g., `pie`, `gantt`, `flowchart`) to visualize trends or relationships.
    5.  **Structure & Formatting**:
        *   Use `##` for main sections and `###` for sub-sections to create a rich, logical structure. This will automatically generate a useful "On this page" TOC.
        *   Start the article with a bold, engaging introductory paragraph.

    [Output Format - Adhere Strictly to this Front Matter]
    ---
    layout: single
    title: "[AI가 생성할 자극적인 제목]"
    date: {now.strftime('%Y-%m-%d %H:%M:%S')}
    categories: ["미국증시"]
    published: false
    toc: true
    ---

    (Start writing the article here in Korean. Begin with a strong hook.)

    ## 1. 거시 경제 브리핑: 시장의 숨은 동력

    ### 금리와 인플레이션

    ## 2. 섹터별 심층 분석: 승자와 패자

    ### 오늘의 주인공

    ### 눈물의 섹터

    ## 3. 시장의 핵심 동인(Key Movers)

    ## 4. 투자 심리 및 VIX 분석

    ## 5. 전망 및 투자 전략

    ## 6. 주요 참고 뉴스
    (List 3-5 most relevant news links from your analysis here. e.g., "- [기사 제목](링크) - 주요 내용 요약")
    """

    try:
        response = model.generate_content(prompt)
        content = response.text.strip()

        if content.startswith("```markdown"): content = content.replace("```markdown", "", 1)
        if content.startswith("```"): content = content.replace("```", "", 1)
        if content.endswith("```"): content = content[:-3]

        return content.strip() + DISCLAIMER_TEXT

    except Exception as e:
        return f"Error: {str(e)}"

def save_and_notify(content):
    if "Error" in content:
        print(f"❌ [API Error] 생성이 중단되었습니다. 원인: {content}")
        return

    today = datetime.datetime.now(SEOUL_TZ).strftime("%Y-%m-%d")
    timestamp = datetime.datetime.now(SEOUL_TZ).strftime("%H%M")
    category_path = "_posts/us-stock"
    os.makedirs(category_path, exist_ok=True)
    filename = f"{category_path}/{today}-market-{timestamp}.md"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        repo = os.environ.get("GITHUB_REPOSITORY", "user/repo")
        url = f"https://github.com/{repo}/blob/main/{filename}"
        msg = f"📝 **[새로운 글 생성 완료]**\n\n내용 확인 후 '/publish' 하세요.\n[미리보기]({url})"

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
            )
            if response.status_code != 200:
                print(f"❌ [Telegram Error] {response.status_code}: {response.text}")
            else:
                print("✅ [Telegram] 알림 전송 성공")
        except Exception as e:
            print(f"❌ [Telegram Exception] {str(e)}")
    else:
        print("⚠️ [Telegram] 토큰 또는 Chat ID가 설정되지 않았습니다.")
        print(f"   - TELEGRAM_TOKEN 설정 여부: {'O' if TELEGRAM_TOKEN else 'X'}")
        print(f"   - TELEGRAM_CHAT_ID 설정 여부: {'O' if TELEGRAM_CHAT_ID else 'X'}")

if __name__ == "__main__":
    data = get_market_data()
    post = generate_blog_post(data)
    save_and_notify(post)