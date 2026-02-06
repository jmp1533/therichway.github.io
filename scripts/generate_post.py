import os
import datetime
import pytz
import yfinance as yf
import google.generativeai as genai
import requests

# --- [환경변수 및 설정] ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "")
SEOUL_TZ = pytz.timezone('Asia/Seoul')

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_market_data():
    """야후 파이낸스 데이터 수집 (^VIX 등 지수 티커 최적화)"""
    tickers = {"^DJI": "다우존스", "^GSPC": "S&P500", "^IXIC": "나스닥", "^VIX": "공포지수"}
    data_str = "현재 미국 증시 데이터:\n"

    for symbol, name in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="7d")
            if not hist.empty and len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change_pct = ((close - prev_close) / prev_close) * 100
                data_str += f"- {name}: {close:.2f} ({change_pct:+.2f}%)\n"
        except Exception as e:
            print(f"⚠️ {symbol} 데이터 수집 에러: {str(e)}")

    return data_str

def generate_blog_post(market_data):
    """검증된 과거 모델(1.5)을 우선적으로 사용하여 분석 수행"""
    if not GEMINI_API_KEY:
        return "Error: API Key missing."

    # [모델 우선순위] 과거의 검증된 모델인 1.5 시리즈를 리스트 상단에 배치합니다.
    # 1.5 Pro는 추론이 깊고, 1.5 Flash는 빠르고 안정적입니다.
    models_to_try = [
        'gemini-2.0-flash',
        'gemini-2.5-flash',
        'gemini-2.5-pro',
        'gemini-3-flash-preview'
    ]

    model_instance = None
    used_model = ""

    for m_name in models_to_try:
        try:
            print(f"🧐 {m_name} 모델(우선순위 기반) 연결 시도 중...")
            test_model = genai.GenerativeModel(m_name)
            # 모델 활성화 여부 즉시 확인
            test_model.generate_content("hi", generation_config={"max_output_tokens": 1})
            model_instance = test_model
            used_model = m_name
            print(f"✅ {m_name} 모델로 분석을 시작합니다.")
            break
        except Exception as e:
            print(f"⚠️ {m_name} 호출 불가 또는 권한 없음: {str(e)}")
            continue

    if not model_instance:
        return "Error: 모든 시도 모델이 사용 불가 상태입니다."

    now = datetime.datetime.now(SEOUL_TZ)
    full_now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    prompt = f"""
    [Identity] 시니어 주식 분석가 'The Rich Way'
    [Data]\n{market_data}
    [Topic] {FOCUS_TOPIC if FOCUS_TOPIC else '일일 미국 증시 종합 리포트'}

    [Task]
    1. 위 데이터를 바탕으로 통찰력 있는 블로그 포스팅을 작성하라.
    2. 데이터 간의 유기적인 흐름을 짚어내어 투자 인사이트를 제공하라.
    3. 본문 마지막에 'Analyzed by {used_model}'을 기재하라.

    [Output Format]
    ---
    layout: post
    title: "[TheRichWay] 오늘의 미국 증시 브리핑"
    date: {full_now_str}
    categories: [경제·재테크, 미국증시]
    published: false
    ---
    (여기에 블로그 본문 작성)
    """

    try:
        response = model_instance.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error during generation: {str(e)}"

def save_and_notify(content):
    if "Error" in content:
        print(f"❌ 작업 중단: {content}")
        return

    # 파일 저장
    today = datetime.datetime.now(SEOUL_TZ).strftime("%Y-%m-%d")
    filename = f"_posts/{today}-analysis.md"
    os.makedirs("_posts", exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 포스팅 파일 저장 완료: {filename}")

    # 텔레그램 알림
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        repo_name = os.environ.get("GITHUB_REPOSITORY", "user/repo")
        issue_url = f"https://github.com/{repo_name}/issues/new?title=approve-{filename}"
        message = (
            f"📊 **[The Rich Way] AI 분석 리포트 완료**\n\n"
            f"검증된 모델로 시황 분석을 마쳤습니다.\n"
            f"내용을 검토하신 후 승인해 주세요.\n\n"
            f"[👉 발행 승인하기]({issue_url})"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})

if __name__ == "__main__":
    market_data = get_market_data()
    post_content = generate_blog_post(market_data)
    save_and_notify(post_content)