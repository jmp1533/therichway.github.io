import os
import datetime
import pytz
import yfinance as yf
import google.generativeai as genai
import requests
import time

# --- 환경변수 및 설정 ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "")
SEOUL_TZ = pytz.timezone('Asia/Seoul')

# Gemini 설정
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_market_data():
    """야후 파이낸스 데이터 수집 (심층 분석용 로우 데이터)"""
    tickers = {"^DJI": "다우존스", "^GSPC": "S&P500", "^IXIC": "나스닥", "VIX": "공포지수"}
    data_str = "현재 미국 증시 및 변동성 데이터:\n"
    for symbol, name in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="7d") # 분석 깊이를 위해 7일치 수집
            if len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change_pct = ((close - prev_close) / prev_close) * 100
                high_7d = hist['High'].max()
                low_7d = hist['Low'].min()
                data_str += (f"- {name}: 종가 {close:.2f} ({change_pct:+.2f}%), "
                             f"7일간 레인지({low_7d:.2f} ~ {high_7d:.2f})\n")
        except Exception as e:
            print(f"⚠️ {symbol} 데이터 수집 중 오류: {e}")
    return data_str

def generate_blog_post(market_data):
    if not GEMINI_API_KEY:
        return "Error: Gemini API Key is missing."

    # 정확도와 추론 능력을 위해 1.5 Pro 및 2.0 Flash를 우선 순위로 설정
    # 무료 티어 내에서 최고의 지능을 가진 모델들입니다.
    models_to_try = [
        'gemini-1.5-pro',       # 추론 능력 최상 (무료 티어 RPM 2회 제한)
        'gemini-2.0-flash',     # 최신 아키텍처, 높은 정확도
        'gemini-1.5-flash'      # 안정적인 백업
    ]

    model = None
    for m_name in models_to_try:
        try:
            print(f"🧐 {m_name} 모델로 심층 분석 시도 중...")
            test_model = genai.GenerativeModel(m_name)
            # 모델 호출 시도 (무료 티어 할당량 체크)
            model = test_model
            break
        except Exception as e:
            print(f"⚠️ {m_name} 사용 불가: {e}")
            time.sleep(10) # 할당량 초과 시 충분히 대기
            continue

    if not model:
        return "Error: 분석을 수행할 수 있는 AI 모델을 찾을 수 없습니다."

    now = datetime.datetime.now(SEOUL_TZ)
    today_date = now.strftime('%Y-%m-%d')
    full_now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # --- 추론 능력 극대화를 위한 프롬프트 고도화 ---
    prompt = f"""
    [Identity]
    당신은 12년 경력의 월 방문자 100만 명을 보유한 수석 주식 분석가 'The Rich Way'입니다.
    당신은 단순한 정보 전달자가 아니라, 시장의 이면을 읽어내는 '전략가'입니다.

    [Task]
    제공된 7일간의 시장 데이터와 이슈를 바탕으로, 지표 간의 '인과관계'를 분석하여 리포트를 작성하세요.

    [Analysis Guide]
    1. 상관관계 분석: 지수(S&P, 나스닥)의 움직임과 VIX(공포지수)의 변동을 연계하여 시장의 심리 상태를 추론하세요.
    2. 데이터 검증: 7일간의 최고치/최저치 대비 현재 종가의 위치를 분석하여 단기 지지선/저항선을 판단하세요.
    3. 논리적 추론: {FOCUS_TOPIC if FOCUS_TOPIC else '현재 거시 경제 상황'}이 지수에 미친 구체적인 영향을 논리적으로 서술하세요.

    [Output Requirements]
    - SEO 키워드: '미국 증시', '나스닥 전망', '오늘의 주식'을 분석 내용에 자연스럽게 포함.
    - 본문 구조:
        - [서론] 시장 시그널 요약 및 오늘의 'Key Sentiment' 정의.
        - [본론 1] 데이터 상세 분석 (마크다운 표 및 분석가 코멘트).
        - [본론 2] 주요 테마 인사이트 (데이터 이면의 뉴스 해석).
        - [결론] 내일의 투자 관전 포인트 및 대응 전략.
    - 전문성 강조: 가벼운 말투보다는 신뢰감 있고 냉철한 어조를 유지하세요.

    [Jekyll Front Matter]
    ---
    layout: post
    title: "[TheRichWay] 제목"
    date: {full_now_str}
    categories: [경제·재테크, 미국증시]
    published: false
    ---
    """

    try:
        # 모델의 창의성을 낮추고 논리성을 높이기 위한 설정(temperature 조절 가능)
        response = model.generate_content(prompt)
        text = response.text.replace("```markdown", "").replace("```", "").strip()
        return text
    except Exception as e:
        return f"Error: {str(e)}"

# save_post 및 send_telegram_alert 함수는 이전과 동일하게 유지...
def save_post(content):
    today = datetime.datetime.now(SEOUL_TZ).strftime("%Y-%m-%d")
    filename = f"{today}-deep-analysis.md"
    filepath = f"_posts/{filename}"
    os.makedirs("_posts", exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filename

def send_telegram_alert(filename):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    repo_name = os.environ.get("GITHUB_REPOSITORY", "the-richway/the-richway.github.io")
    issue_url = f"https://github.com/{repo_name}/issues/new?title=approve-{filename}"
    message = (
        f"🧠 **[수석 분석가 리포트 생성 완료]**\n"
        f"일자: {datetime.datetime.now(SEOUL_TZ).strftime('%Y-%m-%d')}\n"
        f"모델: Gemini 1.5 Pro / 2.0 Flash\n\n"
        f"데이터 이면의 통찰을 확인하고 승인해 주세요.\n"
        f"[👉 승인 및 발행]({issue_url})"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})

if __name__ == "__main__":
    market_data = get_market_data()
    post_content = generate_blog_post(market_data)
    if "Error" not in post_content:
        saved_file = save_post(post_content)
        send_telegram_alert(saved_file)
    else:
        print(f"❌ 분석 실패: {post_content}")
        exit(1)