from news import get_naver_news
from llm_filter import analyze_news_with_llm, should_block_buy

def llm_check(ticker: str, company_name: str) -> bool:
    news_items = get_naver_news(company_name, display=5, sort="date")
    headlines = [item["title"] for item in news_items]

    if not headlines:
        return True

    result = analyze_news_with_llm(
        ticker=ticker,
        company_name=company_name,
        headlines=headlines
    )

    if should_block_buy(result):
        return False

    return True