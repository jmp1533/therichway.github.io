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
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "미국 증시 시황")
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
내용에 오류가 있거나 저작권 문제가 발생할 경우, 즉시 삭제 또는 수정 조치하겠습니다.
</p>
"""

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_market_data():
    """데이터 수집 로직"""
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

def get_gemini_model():
    """최신 모델 우선 선택 로직"""
    models = ['gemini-flash-latest', 'gemini-3-pro-preview', 'gemini-3-flash-preview', 'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            model.generate_content("test", generation_config={"max_output_tokens": 1})
            return model
        except: continue
    return None

def generate_blog_post(market_data):
    if not GEMINI_API_KEY: return "Error: API Key missing."

    model = get_gemini_model()
    if not model: return "Error: No available models."

    now = datetime.datetime.now(SEOUL_TZ)
    date_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # ---------------------------------------------------------
    # [Step 1] 전문 분석가 모드: 글 + 표 + 그림 동시 작성
    # ---------------------------------------------------------
    prompt_analyst = f"""
    [Identity]
    You are a Wall Street Senior Analyst writing for 'TheRichWay'.
    Your tone is professional, insightful, and slightly provocative.

    [Input Data]
    - Market Data: {market_data}
    - Topic: {FOCUS_TOPIC}

    [Mandatory Requirements]
    1. **Content**: Write a deep analysis of the US market trends.
    2. **Visuals (MUST INCLUDE)**:
       - **Markdown Table**: Summarize key indices or sector performance in a table.
       - **Mermaid Chart**: Include at least one `pie` or `graph TD` chart to visualize the data or logic. (Wrap in ```mermaid code blocks)
    3. **Structure**:
       - Start with a market summary.
       - Deep dive into the main topic.
       - End with investment strategy.
    4. **Language**: Korean (Expert level).
    """

    try:
        # 1차 생성: 초안 작성 (데이터 + 시각화)
        draft = model.generate_content(prompt_analyst).text
    except Exception as e:
        return f"Error in Step 1: {str(e)}"

    # ---------------------------------------------------------
    # [Step 2] 편집장 모드: 제목 최적화 + 검수 (Review)
    # ---------------------------------------------------------
    prompt_editor = f"""
    [Role] Chief Editor of a Financial Magazine
    [Input Draft]
    {draft}

    [Task] Polish the draft into a final post.
    1. **Title**: Create a catchy, click-worthy title (e.g., "폭락? 기회? 지금 주목해야 할 시그널").
    2. **Refinement**: Fix typos and ensure natural Korean flow.
    3. **Front Matter**: Ensure STRICT Front Matter format:
    ---
    layout: single
    title: "YOUR_CATCHY_TITLE"
    date: {date_str}
    categories: ["경제·재테크", "미국증시"]
    published: false
    toc: true
    ---

    [Output] Return ONLY the final Markdown content. Do not include introductory text like "Here is the revised version".
    """

    try:
        # 2차 생성: 최종 완성
        final_response = model.generate_content(prompt_editor).text
        content = final_response.strip()

        # Markdown 코드 블록 제거 (Front Matter 보호)
        if content.startswith("```markdown"): content = content.replace("```markdown", "", 1)
        if content.startswith("```"): content = content.replace("```", "", 1)
        if content.endswith("```"): content = content[:-3]

        return content.strip() + DISCLAIMER_TEXT

    except Exception as e:
        return f"Error in Step 2: {str(e)}"

def save_and_notify(content):
    if "Error" in content:
        print(f"❌ [API Error] {content}")
        return

    today = datetime.datetime.now(SEOUL_TZ).strftime("%Y-%m-%d")
    timestamp = datetime.datetime.now(SEOUL_TZ).strftime("%H%M")

    # [수정] 파일 저장 경로: _posts/us-stock/
    category_dir = "_posts/us-stock"
    os.makedirs(category_dir, exist_ok=True)

    filename = f"{today}-market-{timestamp}.md"
    filepath = f"{category_dir}/{filename}"

    # 로컬 저장
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 파일 생성 완료: {filepath}")

    # 텔레그램 알림
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        repo = os.environ.get("GITHUB_REPOSITORY", "user/repo")
        # GitHub URL도 경로에 맞게 수정
        file_url = f"https://github.com/{repo}/blob/main/{filepath}"

        msg = (
            f"📊 **[TheRichWay 미국증시 리포트]**\n"
            f"주제: {FOCUS_TOPIC}\n"
            f"검토 후 발행하세요: `/publish`\n"
            f"[👉 리포트 미리보기]({file_url})"
        )

        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
            )
            print("✅ 텔레그램 발송 성공")
        except Exception as e:
            print(f"❌ 텔레그램 에러: {e}")

if __name__ == "__main__":
    data = get_market_data()
    post = generate_blog_post(data)
    save_and_notify(post)