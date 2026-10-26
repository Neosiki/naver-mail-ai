# -*- coding: utf-8 -*-
# 네이버 메일 AI 정리 비서 (읽기 전용 · 자동 발송 없음)
# 하는 일: 최근 하루 '안 읽은 메일' → AI 분류·요약·답장 초안 → CSV 저장
# 실행:  python naver_mail_ai.py            (CSV + 아침 요약)
#        python naver_mail_ai.py --drafts   (답장 초안을 txt 파일로도 저장)
# AI_PROVIDER (.env에서 고르기)
#   돈 안 드는 방법: keyword(AI 없음) / ollama(내 PC AI) / gemini(무료 키) / codex(ChatGPT 구독)
#   유료 API: openai / anthropic      시험용: mock
import os, sys, csv, json, imaplib, email, datetime, shutil, subprocess
import urllib.request
from email.header import decode_header
from email.utils import parseaddr
from dotenv import load_dotenv          # pip install python-dotenv

load_dotenv()  # 같은 폴더의 .env 파일에서 비밀번호·키를 읽어 옵니다
NAVER_ID = os.environ["NAVER_ID"]               # 예: myshop@naver.com
NAVER_PW = os.environ["NAVER_APP_PASSWORD"]     # 애플리케이션 비밀번호
PROVIDER = os.getenv("AI_PROVIDER", "keyword")  # 위 목록 중 하나
KEY = os.getenv("AI_API_KEY", "")               # openai/anthropic/gemini 만 필요
MODEL = os.getenv("AI_MODEL") or {"openai": "gpt-6-luna",
    "anthropic": "claude-haiku-5-5", "gemini": "gemini-3.5-flash-lite",
    "ollama": "qwen2.5:7b"}.get(PROVIDER, "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

PROMPT = """당신은 작은 가게의 메일 정리 비서입니다. 아래 메일을 읽고
JSON 한 개로만 답하세요. 다른 글은 쓰지 마세요.
{"분류": "예약/주문/문의/견적·세금계산서/광고/기타 중 하나",
 "요약": "핵심 2줄 (날짜·인원·금액은 그대로)",
 "답장초안": "정중한 답장 5문장 이내. 예약 가능 여부·가격·재고처럼
  메일에 없는 사실은 약속하지 말고 [확인 필요]라고 쓰기"}
보낸 사람: %s
제목: %s
본문:
%s"""

# keyword 모드: 이 낱말이 제목·본문에 있으면 그 분류 (위에서부터 먼저 검사)
RULES = [("광고", ["(광고)", "[광고]", "수신거부", "특가", "할인", "이벤트"]),
         ("견적·세금계산서", ["견적", "세금계산서", "계산서", "거래명세서", "청구서"]),
         ("예약", ["예약", "클래스", "방문", "자리", "인원", "몇 시"]),
         ("주문", ["주문", "배송", "택배", "결제", "구매", "교환", "환불"]),
         ("문의", ["문의", "궁금", "가능할까요", "알려주", "?"])]
# keyword 모드 답장 틀 (대표님 가게에 맞게 고쳐 쓰세요. 비우면 초안 없음)
TEMPLATES = {"예약": "안녕하세요. 문의 주셔서 감사합니다. 요청하신 날짜와 인원을 "
                    "[확인 필요] 확인한 뒤 바로 안내드리겠습니다.",
             "주문": "안녕하세요. 주문해 주셔서 감사합니다. 주문 내용을 확인한 뒤 "
                    "배송 일정을 [확인 필요] 안내드리겠습니다.",
             "문의": "안녕하세요. 문의 주셔서 감사합니다. 확인 후 빠르게 답변드리겠습니다."}

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

def by_keyword(subject, body):
    """AI 없이 낱말 규칙으로 분류하고, 본문 앞 2줄을 요약으로 씁니다."""
    text = subject + "\n" + body
    kind = next((k for k, words in RULES if any(w in text for w in words)), "기타")
    lines = [l.strip() for l in body.splitlines() if l.strip()][:2]
    summary = "\n".join(l[:60] for l in lines)        # 한 줄 60자까지만
    return {"분류": kind, "요약": summary, "답장초안": TEMPLATES.get(kind, "")}

KINDS = ["예약", "주문", "문의", "견적·세금계산서", "광고", "기타"]
def tidy(kind):
    """AI가 '견적'처럼 조금 다르게 답해도 정해진 분류 이름으로 맞춥니다."""
    kind = str(kind).strip()
    if kind in KINDS:
        return kind
    if "견적" in kind or "계산서" in kind:
        return "견적·세금계산서"
    return next((k for k in KINDS if k in kind), "기타")

def post(url, data, head):
    """인터넷 주소로 JSON을 보내고 JSON 답을 받습니다."""
    head["Content-Type"] = "application/json"
    req = urllib.request.Request(url, json.dumps(data).encode(), head)
    return json.load(urllib.request.urlopen(req, timeout=120))

def ask_ai(sender, subject, body):
    """고른 방법(PROVIDER)으로 메일을 정리하고 JSON 답을 받습니다."""
    if PROVIDER == "keyword":                       # AI 없이 낱말 규칙
        return by_keyword(subject, body)
    if PROVIDER == "mock":                          # 시험용: AI 없이 가짜 답
        return {"분류": "문의", "요약": "시험 요약입니다.", "답장초안": "시험 답장"}
    text = PROMPT % (sender, subject, body[:3000])  # 너무 긴 본문은 자릅니다
    msgs = [{"role": "user", "content": text}]
    if PROVIDER == "ollama":      # 내 PC 안의 AI. 메일이 밖으로 나가지 않습니다
        res = post(OLLAMA_URL + "/api/chat", {"model": MODEL, "messages": msgs,
                   "format": "json", "stream": False}, {})
        answer = res["message"]["content"]
    elif PROVIDER == "gemini":    # 구글 AI Studio 무료 키
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               + MODEL + ":generateContent")
        res = post(url, {"contents": [{"parts": [{"text": text}]}],
                   "generationConfig": {"responseMimeType": "application/json"}},
                   {"x-goog-api-key": KEY})
        answer = res["candidates"][0]["content"]["parts"][0]["text"]
    elif PROVIDER == "codex":     # ChatGPT 계정으로 로그인한 Codex CLI 실행
        exe = shutil.which("codex")                 # 윈도우의 codex.cmd 도 찾아 줌
        if not exe:
            raise RuntimeError("codex 명령이 없습니다 (npm i -g @openai/codex)")
        # read-only: 파일을 고치지 못하게 / "-": 부탁 글을 키보드 입력(stdin)으로 전달
        run = subprocess.run([exe, "exec", "--sandbox", "read-only",
                              "--skip-git-repo-check", "--ephemeral", "-"],
                             input=text, capture_output=True, text=True,
                             encoding="utf-8", timeout=300)
        if run.returncode != 0:
            raise RuntimeError("codex 오류(codex login 확인): "
                               + run.stderr.strip()[-150:])
        answer = run.stdout
    elif PROVIDER == "anthropic":
        res = post("https://api.anthropic.com/v1/messages",
                   {"model": MODEL, "max_tokens": 800, "messages": msgs},
                   {"x-api-key": KEY, "anthropic-version": "2023-06-01"})
        answer = res["content"][0]["text"]
    else:                         # openai
        res = post("https://api.openai.com/v1/chat/completions",
                   {"model": MODEL, "messages": msgs},
                   {"Authorization": "Bearer " + KEY})
        answer = res["choices"][0]["message"]["content"]
    answer = answer[answer.find("{"): answer.rfind("}") + 1]  # JSON만 골라냄
    result = json.loads(answer)
    result["분류"] = tidy(result.get("분류", ""))
    return result

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
