# 02. 한국투자 API 연결 (토큰 발급 같은 API 인증 담당)

import requests
from config import APP_KEY, APP_SECRET, BASE_URL


def get_token():

    url = f"{BASE_URL}/oauth2/tokenP"

    headers = {
        "content-type": "application/json"
    }

    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }

    res = requests.post(url, headers=headers, json=body)

    token = res.json()["access_token"]

    return token