# 가짜 IMAP 서버 + 가짜 AI 응답으로 naver_mail_ai.py 전체 흐름을 시험합니다.
# 실제 네이버 접속·AI 호출은 하지 않습니다. (인터넷·비밀번호 필요 없음)
# 실행: python tests/test_fake.py openai   또는   python tests/test_fake.py anthropic
import os, sys, io, json, glob, csv, tempfile
from unittest import mock
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.header import Header
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(tempfile.mkdtemp())  # 결과 CSV·drafts는 임시 폴더에 만듭니다
if len(sys.argv) < 2: sys.argv.append("openai")
os.environ.update(NAVER_ID="myshop@naver.com", NAVER_APP_PASSWORD="test-app-pw",
                  AI_PROVIDER=sys.argv[1], AI_API_KEY="sk-test")

def mk(frm, subj, body, charset="utf-8", attach=False):
    m = MIMEMultipart() if attach else MIMEText(body, "plain", charset)
    if attach:
        m.attach(MIMEText(body, "plain", charset))
        a = MIMEApplication(b"%PDF-fake"); a.add_header("Content-Disposition","attachment",filename="견적서.pdf"); m.attach(a)
    m["From"] = "%s <%s>" % (Header(frm[0], charset).encode(), frm[1])
    m["Subject"] = Header(subj, charset).encode()
    m["Date"] = "Mon, 26 Oct 2026 07:12:00 +0900"
    return m.as_bytes()

MAILS = {b"101": mk(("김하늘","sky_kim@naver.com"),"토요일 클래스 문의드려요","토요일 2시에 4명 가능할까요? 주차도 되나요?"),
         b"102": mk(("가죽나라 이영수","sales@gajuk.example"),"[가죽나라] 10월 원단 견적서 송부","공급가 680,000원, 부가세 68,000원, 합계 748,000원입니다.","euc-kr",attach=True),
         b"103": mk(("쇼핑몰광고","ad@promo.example"),"(광고) 가을 특가 70%","지금 바로 확인하세요")}
CALLS = []
class FakeIMAP:
    def __init__(s, host, port): CALLS.append(("connect", host, port))
    def login(s, u, p): CALLS.append(("login", u, p))
    def select(s, box, readonly=False): CALLS.append(("select", box, readonly)); return "OK", [b"3"]
    def search(s, cs, *c): CALLS.append(("search",)+c); return "OK", [b" ".join(MAILS)]
    def fetch(s, n, what): CALLS.append(("fetch", n, what)); return "OK", [(b"x", MAILS[n])]
    def store(s, *a): raise AssertionError("메일을 바꾸면 안 됩니다")
    def expunge(s): raise AssertionError("삭제하면 안 됩니다")
    def logout(s): CALLS.append(("logout",))

ANS = {"토요일": {"분류":"예약","요약":"토요일 오후 2시 원데이 클래스 4명 예약 문의.\n주차 가능 여부도 질문.","답장초안":"김하늘 고객님, 안녕하세요. 토요일 2시 4분 자리는 [확인 필요] 후 바로 안내드리겠습니다. 주차는 건물 뒤 공영주차장을 이용하실 수 있습니다."},
       "가죽나라": {"분류":"견적·세금계산서","요약":"가죽나라 10월 원단 견적, 합계 748,000원.\n공급가 680,000원 · 부가세 68,000원.","답장초안":"이영수 과장님, 견적서 잘 받았습니다. 검토 후 회신드리겠습니다."},
       "광고": {"분류":"광고","요약":"가을 특가 광고 메일.","답장초안":""}}
class Resp(io.BytesIO): pass
def fake_urlopen(req, timeout=0):
    d = json.loads(req.data); txt = d["messages"][0]["content"]
    CALLS.append(("ai", req.full_url, d["model"], req.headers))
    a = next(v for k, v in ANS.items() if k in txt)
    out = "```json\n" + json.dumps(a, ensure_ascii=False) + "\n```"  # 코드블록으로 감싼 답도 처리되는지
    body = {"content":[{"type":"text","text":out}]} if "anthropic" in req.full_url else {"choices":[{"message":{"content":out}}]}
    return Resp(json.dumps(body).encode())

import naver_mail_ai as app
with mock.patch("imaplib.IMAP4_SSL", FakeIMAP), mock.patch("urllib.request.urlopen", fake_urlopen), \
     mock.patch.object(sys, "argv", ["naver_mail_ai.py", "--drafts"]):
    app.main()
assert ("connect","imap.naver.com",993) in CALLS
assert ("select","INBOX",True) in CALLS
assert all(c[2]=="(BODY.PEEK[])" for c in CALLS if c[0]=="fetch")
assert [c for c in CALLS if c[0]=="search"][0][1]=="UNSEEN"
f = glob.glob("메일정리_*.csv")[0]
raw = open(f,"rb").read(); assert raw.startswith(b"\xef\xbb\xbf"), "BOM 없음"
rows = list(csv.reader(open(f, encoding="utf-8-sig")))
assert rows[2][3]=="[가죽나라] 10월 원단 견적서 송부" and rows[2][1]=="가죽나라 이영수", rows[2]
assert rows[1][4]=="예약" and rows[2][4]=="견적·세금계산서"
assert len(glob.glob("drafts/*.txt"))==2
print("--- AI 호출:", [(c[1], c[2]) for c in CALLS if c[0]=="ai"][:1])
print("--- 테스트 통과:", sys.argv[1], f, len(rows)-1, "행 (임시 폴더: %s)" % os.getcwd())
