import os
import datetime
import pytz
import yfinance as yf
import google.generativeai as genai
import requests
import re

# --- [환경변수 및 설정] ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "미국 증시 시황")
SEOUL_TZ = pytz.timezone('Asia/Seoul')

# [디스클레이머: 작은 글씨로 하단에 부착될 문구]
DISCLAIMER_TEXT = """
<br><br>
<hr>
<p style="text-align: center; font-size: 0.9em; color: #888; line-height: 1.6;">
    <strong>[안내 및 면책 조항]</strong><br>
    본 콘텐츠는 인공지능(AI) 모델을 활용하여 생성되었습니다.<br>
    투자의 책임은 전적으로 투자자 본인에게 있으며, 제공된 데이터는 일부 지연되거나 오류가 있을 수 있습니다.<br>
    내용에 오류가 발견되거나 저작권 문제가 발생할 경우, 관리자에게 문의 주시면 즉시 수정 또는 삭제 조치하겠습니다.
</p>
<hr>
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
    models = ['gemini-flash-latest', 'gemini-3-pro-preview', 'gemini-3-flash-preview', 'gemini-2.5-pro', 'gemini-2.5-flash-lite']
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
    weekday = now.weekday() # 0:월, 1:화, ... 6:일

    if weekday == 0:
        analysis_target = "지난 주말(토/일) 이슈 및 금요일 마감 시황 분석"
    elif 1 <= weekday <= 4:
        analysis_target = "전일(어제) 시장 및 밤사이 미국 증시 분석"
    else:
        analysis_target = "최근 마감 시장 분석"

    # ---------------------------------------------------------
    # [Step 1] 프롬프트 고도화 (다중 소스 분석 + 분량 확대)
    # ---------------------------------------------------------
    prompt_analyst = f"""
    [Identity & Persona]
    You are a **World-class Global Economic Analyst and Blogger**. You have a deep understanding of financial markets and the ability to synthesize information from a wide array of sources. Your writing is insightful, balanced, and provides a multi-perspective view.

    [Task]
    Write a **very comprehensive and in-depth** blog post on "{FOCUS_TOPIC}". Your analysis must be based on a synthesis of information from the following premier news sources. You should demonstrate your expertise by cross-referencing different viewpoints and data points from them.

    [News Sources for Analysis]
    **US Sources (10):**
    - The Wall Street Journal
    - Bloomberg
    - Reuters
    - CNBC
    - The New York Times
    - The Financial Times
    - Associated Press (AP)
    - Fox Business
    - MarketWatch
    - Yahoo Finance

    **Korean Sources (10):**
    - 한국경제 (Korea Economic Daily)
    - 매일경제 (Maeil Business Newspaper)
    - 조선일보 (Chosun Ilbo)
    - 중앙일보 (JoongAng Ilbo)
    - 동아일보 (Donga Ilbo)
    - 연합뉴스 (Yonhap News)
    - YTN
    - SBS Biz
    - 머니투데이 (Money Today)
    - 네이버 증권 (Naver Finance)

    [Context]
    - Today: {date_str} (Korea Time)
    - **Analysis Target**: {analysis_target}
    - Input Market Data: {market_data}

    [Requirements]
    1. **Length & Depth (CRITICAL)**:
       - The post must be **extremely detailed**, aiming for **4,000 to 5,000 characters** (excluding spaces).
       - Do not just summarize; provide deep context, historical comparisons, and future implications.
       - Each section should be substantial. For example, when discussing a sector, explain *why* it moved, which specific companies led the move, and what analysts are saying.
    2. **Multi-perspective Analysis**:
       - Do not just list news. Synthesize the information.
       - For a key issue, you might write something like: "While US media like The Wall Street Journal focused on the Fed's inflation concerns, Korean outlets such as 매일경제 highlighted the impact on the won-dollar exchange rate for exporters."
       - Show that you have considered views from both US and Korean perspectives.
    3. **Structure & Headings**:
       - Use engaging Korean subheadings. DO NOT use "Market Pulse", "Deep Dive", etc.
       - Create a logical flow: Introduction -> Broad Market Overview -> Deep Dive into 3-4 Key Themes (with multi-source analysis) -> Outlook & Strategy.
    4. **Visuals**:
       - Include a Markdown Table for key data.
       - Include one Mermaid chart to illustrate a key concept or trend.
    5. **References (CRITICAL)**:
       - Title: "## 📚 주요 참고 뉴스"
       - **Generate a list of 5-7 key news articles** that you theoretically used for your analysis.
       - **The URLs must be plausible and point to the correct news domain.** For example, a Wall Street Journal link should start with `https://www.wsj.com/`.
       - **This is a test of your ability to generate realistic, relevant links based on the day's news.** Do not invent fake news, but find plausible real news headlines and construct URLs.
    6. **Tags**:
       - Title: "### 🏷️ 태그"
       - Generate 5 relevant hashtags.

    [Language]: Korean (Professional, High-quality, Analytical).
    """

    draft = ""
    try:
        draft = model.generate_content(prompt_analyst).text
    except Exception as e:
        return f"Error in Step 1: {str(e)}"

    # ---------------------------------------------------------
    # [Step 2] 편집장 모드
    # ---------------------------------------------------------
    prompt_editor = f"""
    [Role] Chief Editor
    [Input Draft]
    {draft}

    [Task] Final Polish.
    1. **Length Check**: Ensure the content is substantial (aiming for 4000-5000 chars). If it feels short, expand on the analysis.
    2. **Link Check**: Ensure ALL links are plausible and direct to the correct domain.
    3. **Formatting**: Ensure Tables/Mermaid are correct.
    4. **Tone Check**: Ensure it sounds like a professional economic blog.
    5. **Header Check**: Ensure NO generic headers like "Market Pulse" exist.
    6. **Front Matter**:
    ---
    layout: single
    title: "YOUR_CATCHY_TITLE_BASED_ON_CONTENT"
    date: {date_str}
    categories: ["경제·재테크", "미국증시"]
    published: true
    toc: true
    ---

    [Output] Return ONLY the final Markdown content.
    """

    try:
        final_response = model.generate_content(prompt_editor).text
        content = final_response.strip()

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

    category_dir = "_posts/us-stock"
    os.makedirs(category_dir, exist_ok=True)

    filename = f"{today}-market-{timestamp}.md"
    filepath = f"{category_dir}/{filename}"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 포스팅 파일 생성 완료: {filepath}")

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        title_match = re.search(r'title:\s*"(.*?)"', content)
        post_title = title_match.group(1) if title_match else "제목 없음"

        msg = (
            f"[미국 증시 리포트 생성]\n"
            f"{post_title}\n\n"
            f"/publish"
        )

        try:
            api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            response = requests.post(
                api_url,
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}
            )
            if response.status_code == 200:
                print("✅ 텔레그램 알림 전송 성공")
            else:
                print(f"❌ 텔레그램 전송 실패: {response.text}")
        except Exception as e:
            print(f"❌ 텔레그램 연결 에러: {e}")

if __name__ == "__main__":
    market_data = get_market_data()
    post = generate_blog_post(market_data)
    save_and_notify(post)