#01. API KEY, 계좌번호와 같은 설정을 넣음

import os
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")

ACCOUNT = os.getenv("ACCOUNT")
ACCOUNT_CODE = os.getenv("ACCOUNT_CODE")

BASE_URL = "https://openapivts.koreainvestment.com:29443"  # 모의투자

TICKER = "005930"  # 삼성전자
