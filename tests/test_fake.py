# 가짜 IMAP 메일함으로 naver_mail_ai.py 전체 흐름을 시험합니다. (네이버 접속 없음)
# 실행: python tests/test_fake.py            → 모든 방법을 차례로 시험
#       python tests/test_fake.py keyword    → 한 가지만
#       python tests/test_fake.py ollama-live → 내 PC에 켜 둔 Ollama로 실제 AI 분류
# AI 부분: keyword·ollama-live 는 실제로 실행, 나머지(openai·anthropic·gemini·
#          ollama·codex)는 각 회사 형식의 '가짜 응답'으로 대신합니다.
import os, sys, io, json, glob, csv, tempfile, importlib
from unittest import mock
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.header import Header
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

def mk(frm, subj, body, charset="utf-8", attach=False):
    m = MIMEMultipart() if attach else MIMEText(body, "plain", charset)
    if attach:
        m.attach(MIMEText(body, "plain", charset))
        a = MIMEApplication(b"%PDF-fake")
        a.add_header("Content-Disposition", "attachment", filename="견적서.pdf")
        m.attach(a)
    m["From"] = "%s <%s>" % (Header(frm[0], charset).encode(), frm[1])
    m["Subject"] = Header(subj, charset).encode()
    m["Date"] = "Mon, 26 Oct 2026 07:12:00 +0900"
    return m.as_bytes()

# 예시 메일 3통: UTF-8 예약 문의 / EUC-KR + 첨부 견적 메일 / 광고
MAILS = {b"101": mk(("김하늘", "sky_kim@naver.com"), "토요일 클래스 문의드려요",
                    "토요일 2시에 4명 가능할까요? 주차도 되나요?"),
         b"102": mk(("가죽나라 이영수", "sales@gajuk.example"), "[가죽나라] 10월 원단 견적서 송부",
                    "공급가 680,000원, 부가세 68,000원, 합계 748,000원입니다.", "euc-kr", attach=True),
         b"103": mk(("쇼핑몰광고", "ad@promo.example"), "(광고) 가을 특가 70%", "지금 바로 확인하세요")}
CALLS = []
class FakeIMAP:
    def __init__(s, host, port): CALLS.append(("connect", host, port))
    def login(s, u, p): CALLS.append(("login", u))
    def select(s, box, readonly=False): CALLS.append(("select", box, readonly)); return "OK", [b"3"]
    def search(s, cs, *c): CALLS.append(("search",) + c); return "OK", [b" ".join(MAILS)]
    def fetch(s, n, what): CALLS.append(("fetch", n, what)); return "OK", [(b"x", MAILS[n])]
    def store(s, *a): raise AssertionError("메일을 바꾸면 안 됩니다")
    def expunge(s): raise AssertionError("삭제하면 안 됩니다")
    def logout(s): CALLS.append(("logout",))

ANS = {"토요일": {"분류": "예약", "요약": "토요일 오후 2시 원데이 클래스 4명 예약 문의.\n주차 가능 여부도 질문.",
                  "답장초안": "김하늘 고객님, 안녕하세요. 토요일 2시 4분 자리는 [확인 필요] 후 바로 안내드리겠습니다."},
       "가죽나라": {"분류": "견적·세금계산서", "요약": "가죽나라 10월 원단 견적, 합계 748,000원.\n공급가 680,000원 · 부가세 68,000원.",
                    "답장초안": "이영수 과장님, 견적서 잘 받았습니다. 검토 후 회신드리겠습니다."},
       "광고": {"분류": "광고", "요약": "가을 특가 광고 메일.", "답장초안": ""}}
def answer_for(text):
    a = next(v for k, v in ANS.items() if k in text)
    return "```json\n" + json.dumps(a, ensure_ascii=False) + "\n```"  # 코드블록으로 감싼 답도 처리되는지

def fake_urlopen(req, timeout=0):
    d = json.loads(req.data); url = req.full_url
    CALLS.append(("http", url, d, dict(req.header_items())))
    if "generativelanguage" in url:
        out = answer_for(d["contents"][0]["parts"][0]["text"])
        body = {"candidates": [{"content": {"parts": [{"text": out}]}}]}
    else:
        out = answer_for(d["messages"][0]["content"])
        if "anthropic" in url: body = {"content": [{"type": "text", "text": out}]}
        elif "/api/chat" in url: body = {"message": {"role": "assistant", "content": out}}
        else: body = {"choices": [{"message": {"content": out}}]}
    return io.BytesIO(json.dumps(body).encode())

def fake_run(args, input=None, **kw):
    CALLS.append(("run", args, kw.get("timeout")))
    return mock.Mock(returncode=0, stdout="작업 완료\n" + answer_for(input), stderr="")

def run(mode):
    provider = mode.replace("-live", "")
    os.environ.update(NAVER_ID="myshop@naver.com", NAVER_APP_PASSWORD="test-app-pw",
                      AI_PROVIDER=provider, AI_API_KEY="test-key")
    os.environ.pop("AI_MODEL", None)
    if mode == "ollama-live": os.environ["AI_MODEL"] = os.getenv("LIVE_MODEL", "qwen2.5:1.5b")
    CALLS.clear(); os.chdir(tempfile.mkdtemp())     # 결과는 임시 폴더에
    import naver_mail_ai as app; importlib.reload(app)  # .env 값을 새로 읽게
    patches = [mock.patch("imaplib.IMAP4_SSL", FakeIMAP),
               mock.patch.object(sys, "argv", ["naver_mail_ai.py", "--drafts"])]
    if mode not in ("keyword", "ollama-live"):
        patches += [mock.patch("urllib.request.urlopen", fake_urlopen),
                    mock.patch("subprocess.run", fake_run),
                    mock.patch("shutil.which", lambda n: "/usr/local/bin/" + n)]
    print("\n$ AI_PROVIDER=%s python naver_mail_ai.py --drafts" % provider)
    for p in patches: p.start()
    try: app.main()
    finally:
        for p in patches: p.stop()
    # 공통 확인: 접속 정보 · 읽기 전용 · 몰래 보기 · CSV 한글
    assert ("connect", "imap.naver.com", 993) in CALLS
    assert ("select", "INBOX", True) in CALLS
    assert all(c[2] == "(BODY.PEEK[])" for c in CALLS if c[0] == "fetch")
    f = glob.glob("메일정리_*.csv")[0]
    assert open(f, "rb").read().startswith(b"\xef\xbb\xbf"), "BOM 없음"
    rows = list(csv.reader(open(f, encoding="utf-8-sig")))[1:]
    assert len(rows) == 3 and rows[1][3] == "[가죽나라] 10월 원단 견적서 송부" and rows[1][1] == "가죽나라 이영수"
    kinds = [r[4] for r in rows]
    if mode == "ollama-live":   # 진짜 AI: 결과가 정해진 분류 중 하나이고 오류가 없으면 통과
        assert all(k in ["예약", "주문", "문의", "견적·세금계산서", "광고", "기타"] for k in kinds), kinds
        assert not any(r[5].startswith("AI 오류") for r in rows), rows
    else:
        assert kinds == ["예약", "견적·세금계산서", "광고"], kinds
    drafts = len(glob.glob("drafts/*.txt"))
    assert drafts == (1 if mode == "keyword" else 2 if mode != "ollama-live" else drafts)
    # 방법별 확인
    http = [c for c in CALLS if c[0] == "http"]
    if provider == "gemini":
        assert "models/gemini-3.5-flash-lite:generateContent" in http[0][1]
        assert http[0][3].get("X-goog-api-key") == "test-key"
        assert http[0][2]["generationConfig"]["responseMimeType"] == "application/json"
    if mode == "ollama":
        assert http[0][1] == "http://localhost:11434/api/chat"
        assert http[0][2]["format"] == "json" and http[0][2]["stream"] is False
        assert http[0][2]["model"] == "qwen2.5:7b"
    if provider == "codex":
        r = [c for c in CALLS if c[0] == "run"][0]
        assert r[1][1:] == ["exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral", "-"], r[1]
        assert r[2] == 300
    if mode == "keyword": assert not http
    print("--- 통과: %s · CSV %d행 · 분류 %s · 초안 %d개" % (mode, len(rows), "/".join(kinds), drafts))

if __name__ == "__main__":
    modes = sys.argv[1:] or ["keyword", "openai", "anthropic", "gemini", "ollama", "codex"]
    for m in modes: run(m)
