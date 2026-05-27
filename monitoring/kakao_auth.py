"""
카카오 최초 인증 스크립트 — 처음 한 번만 실행하면 됩니다.

사전 준비:
  1. https://developers.kakao.com 접속
  2. 내 애플리케이션 → 애플리케이션 추가
  3. 앱 이름 자유 입력 후 저장
  4. 앱 설정 → 카카오 로그인 → 활성화 ON
  5. 카카오 로그인 → Redirect URI 에  https://localhost  추가
  6. 앱 키 → REST API 키 복사 → .env 의 KAKAO_REST_API_KEY 에 입력
  7. 이 스크립트 실행: python monitoring/kakao_auth.py
"""
import os
import sys
import webbrowser
import requests
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv, set_key

# 프로젝트 루트 기준 .env 경로
_ROOT    = os.path.join(os.path.dirname(__file__), "..")
_ENV     = os.path.join(_ROOT, ".env")
load_dotenv(_ENV)

REDIRECT_URI = "https://localhost"
AUTH_URL     = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL    = "https://kauth.kakao.com/oauth/token"


def main():
    rest_api_key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    if not rest_api_key:
        print("❌  .env 파일에 KAKAO_REST_API_KEY 가 없습니다.")
        print("    developers.kakao.com → 앱 키 → REST API 키를 복사해 입력하세요.")
        rest_api_key = input("REST API 키 입력: ").strip()
        set_key(_ENV, "KAKAO_REST_API_KEY", rest_api_key)

    auth_url = (
        f"{AUTH_URL}"
        f"?client_id={rest_api_key}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=talk_message"
    )

    print("\n브라우저가 열립니다. 카카오 로그인 후 주소창의 URL 전체를 복사하세요.")
    print(f"(자동으로 열리지 않으면 아래 URL을 직접 열어주세요)\n{auth_url}\n")
    webbrowser.open(auth_url)

    redirected = input("로그인 완료 후 브라우저 주소창 URL 붙여넣기: ").strip()

    try:
        code = parse_qs(urlparse(redirected).query).get("code", [None])[0]
        if not code:
            raise ValueError("code 파라미터를 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌  URL 파싱 실패: {e}")
        sys.exit(1)

    res = requests.post(TOKEN_URL, data={
        "grant_type":   "authorization_code",
        "client_id":    rest_api_key,
        "redirect_uri": REDIRECT_URI,
        "code":         code,
    }, timeout=10)

    data = res.json()
    if "access_token" not in data:
        print(f"❌  토큰 발급 실패: {data}")
        sys.exit(1)

    set_key(_ENV, "KAKAO_ACCESS_TOKEN",  data["access_token"])
    set_key(_ENV, "KAKAO_REFRESH_TOKEN", data.get("refresh_token", ""))

    print("\n✅  인증 완료! .env 에 토큰이 저장됐습니다.")
    print("    이제 python main.py 를 실행하면 카카오톡으로 알림이 옵니다.")


if __name__ == "__main__":
    main()
