import smtplib
import os
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

email    = os.getenv("GMAIL_ADDRESS")
password = os.getenv("GMAIL_APP_PASSWORD")

print(f"이메일  : {email}")
print(f"비밀번호: {password[:4]}****")
print("SMTP 연결 시도 중...")

try:
    msg = MIMEText("KIS 자동매매 Gmail 테스트", "plain", "utf-8")
    msg["Subject"] = "[자동매매] 테스트 메일"
    msg["From"]    = email
    msg["To"]      = email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        print("서버 연결 성공")
        smtp.login(email, password)
        print("로그인 성공")
        smtp.sendmail(email, email, msg.as_string())
        print("전송 성공! Gmail 받은편지함을 확인하세요.")

except smtplib.SMTPAuthenticationError as e:
    print(f"인증 실패: {e}")
    print("→ 앱 비밀번호가 맞는지, 2단계 인증이 켜져있는지 확인하세요.")
except Exception as e:
    print(f"오류 발생: {e}")
