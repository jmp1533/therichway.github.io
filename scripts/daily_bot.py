import os
import datetime
import pytz
import yfinance as yf
import google.generativeai as genai
import requests
import time

# --- 환경변수 로드 ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "")

# Gemini 설정
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_market_data():
    tickers = {"^DJI": "다우존스", "^GSPC": "S&P500", "^IXIC": "나스닥"}
    data_str = "최근 미국 증시 데이터:\n"
    for symbol, name in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")
            if len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change_pct = ((close - prev_close) / prev_close) * 100
                data_str += f"- {name}: {close:.2f} ({change_pct:+.2f}%)\n"
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    return data_str

def generate_blog_post(market_data):
    if not GEMINI_API_KEY:
        return "Error: Gemini API Key is missing."

    # [핵심 변경] Pro 모델 삭제! 가볍고 빠른 Flash 모델만 사용
    # 1.5-flash: 현재 주력 무료/고성능 모델
    # 1.5-flash-8b: 더 가벼운 모델 (백업용)
    models_to_try = [
        'gemini-1.5-flash',
        'gemini-1.5-flash-8b',
        'gemini-1.5-flash-latest'
    ]

    model = None
    active_model_name = ""

    # 모델 연결 테스트
    for m_name in models_to_try:
        try:
            print(f"Testing model: {m_name}...")
            test_model = genai.GenerativeModel(m_name)
            # 헬스 체크 (토큰 소모 최소화)
            test_model.generate_content("Hi")
            model = test_model
            active_model_name = m_name
            print(f"✅ Success! Using model: {active_model_name}")
            break
        except Exception as e:
            print(f"⚠️ Failed to use {m_name}: {e}")
            time.sleep(1) # 1초 대기 후 재시도
            continue

    if not model:
        return "Error: 모든 Flash 모델 연결에 실패했습니다. API 키를 확인해주세요."

    today_date = datetime.datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')

    base_instruction = "위 데이터를 바탕으로 오늘자 미국 증시 시황을 분석해줘."

    # 수동 주제가 있으면 반영
    if FOCUS_TOPIC:
        print(f"🎯 Focus Topic Detected: {FOCUS_TOPIC}")
        base_instruction = f"위 데이터도 참고하되, 특히 **'{FOCUS_TOPIC}'** 이슈를 중점적으로 심층 분석해줘. 제목도 이 주제와 관련지어 짓고."

    prompt = f"""
    [Role] 월 방문자 100만 명의 미국 주식 파워 블로거 'The Rich Way'
    [Data] {market_data}
    [Date] {today_date}
    [Task] {base_instruction}
    [Format]
    - Front Matter 필수:
    ---
    layout: post
    title: "AI가 생성한 제목(이모지포함)"
    date: {datetime.datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')}
    categories: [미국주식]
    published: false
    ---
    - 글 구조: 서론(시장 분위기) -> 본론(지수/뉴스 분석) -> 결론(한줄 요약)
    - 스타일: 가독성 좋고 위트 있게 (전문 용어는 쉽게 풀어서)
    """

    try:
        response = model.generate_content(prompt)
        # 마크다운 코드 블록 제거 및 정리
        text = response.text.replace("```markdown", "").replace("```", "")
        return text
    except Exception as e:
        return f"Error generating content: {e}"

def save_post(content):
    seoul_tz = pytz.timezone('Asia/Seoul')
    today = datetime.datetime.now(seoul_tz).strftime("%Y-%m-%d")
    filename = f"{today}-market-analysis.md"
    filepath = f"_posts/{filename}"

    os.makedirs("_posts", exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filename

def send_telegram_alert(filename):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    repo_name = os.environ.get("GITHUB_REPOSITORY", "jmp1533/therichway.github.io")
    issue_title = f"approve-{filename}"
    # 승인 링크 생성
    approve_url = f"https://github.com/{repo_name}/issues/new?title={issue_title}&body=Click+Submit+to+publish."

    message = (
        f"⚡ **[Flash 포스팅 생성 완료]**\n"
        f"주제: {FOCUS_TOPIC if FOCUS_TOPIC else '정기 시황'}\n"
        f"파일: `{filename}`\n\n"
        f"[👉 여기를 눌러 승인(발행)하기]({approve_url})"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Telegram Error: {e}")

if __name__ == "__main__":
    print("Collecting data...")
    data = get_market_data()

    print("Generating content...")
    post = generate_blog_post(data)

    if "Error" not in post:
        saved_file = save_post(post)
        print(f"Saved: {saved_file}")
        send_telegram_alert(saved_file)
    else:
        print(f"❌ CRITICAL ERROR: {post}")
        exit(1) # 강제 실패 처리