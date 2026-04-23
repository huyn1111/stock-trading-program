import os
import requests
from dotenv import load_dotenv

load_dotenv()

_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID")
_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
_URL = "https://openapi.naver.com/v1/search/news.json"


def get_naver_news(company_name: str, display: int = 5, sort: str = "date") -> list[dict]:
    """
    네이버 뉴스 API로 종목명 관련 최신 헤드라인 반환.
    반환: [{"title": str, "pubDate": str, ...}, ...]
    """
    if not _CLIENT_ID or not _CLIENT_SECRET:
        return []

    headers = {
        "X-Naver-Client-Id":     _CLIENT_ID,
        "X-Naver-Client-Secret": _CLIENT_SECRET,
    }
    params = {
        "query":   company_name,
        "display": display,
        "start":   1,
        "sort":    sort,
    }

    try:
        res = requests.get(_URL, headers=headers, params=params, timeout=5)
        if res.status_code == 200:
            return res.json().get("items", [])
    except Exception:
        pass
    return []
