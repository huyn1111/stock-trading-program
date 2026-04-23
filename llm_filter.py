import os
import json
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()


def get_llm_model():
    """
    OpenAI chat model 초기화
    - temperature=0 : 답변 흔들림 줄이기
    - max_tokens=120 : 출력 길이 제한해서 비용 절약
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 없습니다. .env 파일을 확인하세요.")

    model = init_chat_model(
        "gpt-4o-mini",
        model_provider="openai",
        api_key=api_key,
        temperature=0,
        max_tokens=120,
    )
    return model


def build_prompt(ticker: str, company_name: str, headlines: list[str]) -> str:
    """
    뉴스 제목 리스트를 LLM에 넣기 위한 프롬프트 생성
    """
    if not headlines:
        return f"""
You are a stock risk classifier.

Company: {company_name}
Ticker: {ticker}

There are no news headlines.

Return JSON only with:
{{
  "sentiment": "neutral",
  "risk_level": "medium",
  "summary": "No recent headlines were provided."
}}
""".strip()

    headline_text = "\n".join([f"{i+1}. {h}" for i, h in enumerate(headlines)])

    prompt = f"""
You are a stock-news risk classifier.

Your task:
Read the following news headlines for a stock and classify the short-term trading risk.

Company: {company_name}
Ticker: {ticker}

News headlines:
{headline_text}

Rules:
1. Focus on short-term trading risk.
2. Return JSON only.
3. sentiment must be one of: "positive", "neutral", "negative"
4. risk_level must be one of: "low", "medium", "high"
5. summary must be one short sentence.
6. Do not add markdown, code fences, or extra explanation.

JSON format:
{{
  "sentiment": "...",
  "risk_level": "...",
  "summary": "..."
}}
""".strip()

    return prompt


def safe_parse_json(text: str) -> dict:
    """
    LLM 응답이 약간 지저분해도 최대한 JSON으로 파싱
    """
    text = text.strip()

    # 혹시 ```json ... ``` 형태면 제거
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 실패하면 최소한의 fallback
        return {
            "sentiment": "neutral",
            "risk_level": "medium",
            "summary": f"JSON parse failed. Raw output: {text[:100]}"
        }


def analyze_news_with_llm(ticker: str, company_name: str, headlines: list[str]) -> dict:
    """
    뉴스 제목 리스트를 넣으면
    sentiment / risk_level / summary 반환
    """
    model = get_llm_model()
    prompt = build_prompt(ticker, company_name, headlines)
    response = model.invoke(prompt)

    # LangChain chat model 응답은 보통 .content 에 있음
    raw_text = response.content if hasattr(response, "content") else str(response)
    result = safe_parse_json(raw_text)

    # 형식 보정
    sentiment = result.get("sentiment", "neutral")
    risk_level = result.get("risk_level", "medium")
    summary = result.get("summary", "")

    valid_sentiments = {"positive", "neutral", "negative"}
    valid_risks = {"low", "medium", "high"}

    if sentiment not in valid_sentiments:
        sentiment = "neutral"
    if risk_level not in valid_risks:
        risk_level = "medium"

    return {
        "ticker": ticker,
        "company_name": company_name,
        "sentiment": sentiment,
        "risk_level": risk_level,
        "summary": summary,
        "raw_response": raw_text,
    }


def should_block_buy(llm_result: dict) -> bool:
    """
    high 리스크면 매수 차단
    """
    return llm_result.get("risk_level") == "high"


if __name__ == "__main__":
    # 테스트용 예시
    sample_headlines = [
        "Samsung Electronics reports stronger-than-expected quarterly earnings",
        "Foreign investors continue net buying in semiconductor stocks",
        "Market worries remain over memory chip demand slowdown"
    ]

    result = analyze_news_with_llm(
        ticker="005930",
        company_name="Samsung Electronics",
        headlines=sample_headlines
    )

    print("LLM 분석 결과:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if should_block_buy(result):
        print("매수 보류")
    else:
        print("매수 가능")