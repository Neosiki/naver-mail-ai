# -*- coding: utf-8 -*-
# 네이버 메일 AI 정리 비서 (읽기 전용 · 자동 발송 없음)
# 하는 일: 최근 하루 '안 읽은 메일' → AI 분류·요약·답장 초안 → CSV 저장
# 실행:  python naver_mail_ai.py            (CSV + 아침 요약)
#        python naver_mail_ai.py --drafts   (답장 초안을 txt 파일로도 저장)
import os, sys, csv, json, imaplib, email, datetime, urllib.request
from email.header import decode_header
from email.utils import parseaddr
from dotenv import load_dotenv          # pip install python-dotenv

load_dotenv()  # 같은 폴더의 .env 파일에서 비밀번호·키를 읽어 옵니다
NAVER_ID = os.environ["NAVER_ID"]               # 예: myshop@naver.com
NAVER_PW = os.environ["NAVER_APP_PASSWORD"]     # 애플리케이션 비밀번호
PROVIDER = os.getenv("AI_PROVIDER", "openai")   # openai / anthropic / mock
KEY = os.getenv("AI_API_KEY", "")
MODEL = os.getenv("AI_MODEL") or {"openai": "gpt-6-luna",
                                  "anthropic": "claude-haiku-5-5"}.get(PROVIDER, "")

PROMPT = """당신은 작은 가게의 메일 정리 비서입니다. 아래 메일을 읽고
JSON 한 개로만 답하세요. 다른 글은 쓰지 마세요.
{"분류": "예약/주문/문의/견적·세금계산서/광고/기타 중 하나",
 "요약": "핵심 2줄 (날짜·인원·금액은 그대로)",
 "답장초안": "정중한 답장 5문장 이내. 모르는 내용은 [확인 필요]"}
보낸 사람: %s
제목: %s
본문:
%s"""

def to_text(raw):
    """=?UTF-8?B?...?= 처럼 암호처럼 보이는 한글 제목을 사람이 읽는 글로"""
    out = ""
    for part, enc in decode_header(raw or ""):
        if isinstance(part, bytes):
            out += part.decode(enc or "utf-8", errors="replace")
        else:
            out += part
    return out

def body_of(msg):
    """메일 본문(글자 부분)만 꺼냅니다. 첨부파일은 건너뜁니다."""
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and not part.get_filename():
            data = part.get_payload(decode=True) or b""
            return data.decode(part.get_content_charset() or "utf-8", "replace")
    return "(글자 본문 없음)"

def ask_ai(sender, subject, body):
    """AI에게 메일을 보내고 JSON 답을 받습니다."""
    text = PROMPT % (sender, subject, body[:3000])  # 너무 긴 본문은 자릅니다
    if PROVIDER == "mock":                          # 시험용: AI 없이 가짜 답
        return {"분류": "문의", "요약": "시험 요약입니다.", "답장초안": "시험 답장"}
    if PROVIDER == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        head = {"x-api-key": KEY, "anthropic-version": "2023-06-01"}
        data = {"model": MODEL, "max_tokens": 800,
                "messages": [{"role": "user", "content": text}]}
    else:
        url = "https://api.openai.com/v1/chat/completions"
        head = {"Authorization": "Bearer " + KEY}
        data = {"model": MODEL, "messages": [{"role": "user", "content": text}]}
    head["Content-Type"] = "application/json"
    req = urllib.request.Request(url, json.dumps(data).encode(), head)
    res = json.load(urllib.request.urlopen(req, timeout=60))
    if PROVIDER == "anthropic":
        answer = res["content"][0]["text"]
    else:
        answer = res["choices"][0]["message"]["content"]
    answer = answer[answer.find("{"): answer.rfind("}") + 1]  # JSON만 골라냄
    return json.loads(answer)

def main():
    save_drafts = "--drafts" in sys.argv
    box = imaplib.IMAP4_SSL("imap.naver.com", 993)    # SSL 보안 연결
    box.login(NAVER_ID, NAVER_PW)
    box.select("INBOX", readonly=True)                # 읽기 전용: 삭제·변경 불가
    since = (datetime.date.today() - datetime.timedelta(days=1))
    since = since.strftime("%d-%b-%Y")               # 예: 25-Oct-2026
    _, ids = box.search(None, "UNSEEN", "SINCE", since)
    rows = []
    for num in ids[0].split():
        # BODY.PEEK = 몰래 보기. 메일이 '읽음'으로 바뀌지 않습니다
        _, data = box.fetch(num, "(BODY.PEEK[])")
        msg = email.message_from_bytes(data[0][1])
        name, addr = parseaddr(to_text(msg["From"]))
        subject = to_text(msg["Subject"])
        try:
            ai = ask_ai(name or addr, subject, body_of(msg))
        except Exception as e:                        # AI 오류가 나도 계속
            ai = {"분류": "기타", "요약": "AI 오류: %s" % e, "답장초안": ""}
        rows.append([to_text(msg["Date"]), name or addr, addr, subject,
                     ai.get("분류", ""), ai.get("요약", ""), ai.get("답장초안", "")])
        if save_drafts and ai.get("답장초안"):        # 초안은 파일로만 저장
            os.makedirs("drafts", exist_ok=True)
            with open("drafts/%s.txt" % num.decode(), "w", encoding="utf-8") as f:
                f.write("받는 사람: %s\n제목: Re: %s\n\n%s"
                        % (addr, subject, ai["답장초안"]))
    box.logout()
    # 엑셀에서 한글이 깨지지 않도록 utf-8-sig 로 저장합니다
    fname = "메일정리_%s.csv" % datetime.date.today().isoformat()
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["받은시각", "보낸사람", "주소", "제목", "분류", "요약", "답장초안"])
        w.writerows(rows)
    # 아침 요약: 광고는 개수만, 나머지는 한 줄씩
    ads = [r for r in rows if r[4] == "광고"]
    print("☀ %s 아침 메일 요약 · 안 읽은 메일 %d통 (광고 %d통)"
          % (datetime.date.today(), len(rows), len(ads)))
    for r in rows:
        if r[4] != "광고":
            print(" [%s] %s · %s" % (r[4], r[1], r[5].replace("\n", " ")))
    print("→ 저장: %s%s" % (fname, " / 답장 초안: drafts 폴더" if save_drafts else ""))

if __name__ == "__main__":
    main()
