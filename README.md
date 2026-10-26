# 네이버 메일 AI 정리 비서 (naver-mail-ai)

소상공인 대표님을 위한 **네이버 메일 + AI 자동 정리** 파이썬 예제입니다.
매일 아침 한 번 실행하면 **어제부터 온 안 읽은 메일**을 AI가 읽고

- **분류**: 예약 / 주문 / 문의 / 견적·세금계산서 / 광고 / 기타
- **요약**: 핵심 2줄
- **답장 초안**: 정중한 답장 (모르는 내용은 `[확인 필요]` 표시)

을 만들어 **엑셀에서 바로 열리는 CSV 파일**로 저장하고, 화면에 아침 요약을 보여 줍니다.

> 🔒 **안심 설계** — 메일함을 *읽기 전용*으로 열고, `BODY.PEEK`로 읽어 *읽음 표시도 바뀌지 않으며*,
> 메일을 *지우거나 보내지 않습니다*. 답장은 초안만 만들고 보내기는 대표님이 직접 하세요.

---

## 1. 준비물

| 준비물 | 설명 |
| --- | --- |
| PC (윈도우 또는 맥) | 네이버 IMAP 설정은 PC에서만 할 수 있습니다 |
| 파이썬 3.9 이상 | [python.org](https://www.python.org/downloads/) 에서 설치 |
| 네이버 계정 + 스마트폰 | 2단계 인증에 네이버 앱이 깔린 휴대폰이 필요합니다 |
| AI (선택) | **돈 안 드는 4가지 방법**(keyword · Ollama · Gemini 무료 키 · Codex) 또는 유료 API(OpenAI · Anthropic). 아래 비교표 참고 |

## 2. 네이버 IMAP · 애플리케이션 비밀번호 설정

2025년 6월 24일부터 네이버는 외부 프로그램 접속 시 **2단계 인증 + 애플리케이션 비밀번호**를 반드시 요구합니다.
평소 로그인 비밀번호로는 접속되지 않습니다.

1. **IMAP 켜기** — PC 네이버 메일 → 왼쪽 아래 **환경설정** → **POP3/IMAP 설정** → **IMAP/SMTP 설정** 탭 → `사용함` → 저장
2. **2단계 인증 켜기** — 네이버 오른쪽 위 **내 아이디(네이버ID)** → **보안설정** → **2단계 인증** 설정
3. **애플리케이션 비밀번호 만들기** — 네이버ID → 보안설정 → 기본보안설정 → 2단계 인증 → **관리** → 애플리케이션 비밀번호 관리 → 이름 입력(예: `메일비서`) → 생성
   - 생성된 비밀번호는 **다시 볼 수 없으니** 바로 복사해 두세요.

서버 정보 (네이버 메일 고객센터 기준)

| 구분 | 서버 | 포트 | 보안 |
| --- | --- | --- | --- |
| 읽기 IMAP | `imap.naver.com` | 993 | SSL/TLS |
| 보내기 SMTP (이 코드는 사용 안 함) | `smtp.naver.com` | 587 / 465 | STARTTLS / SSL |

## 3. 설치

```bash
# 1) 이 저장소 내려받기 (또는 GitHub에서 Code → Download ZIP)
git clone https://github.com/Neosiki/naver-mail-ai.git
cd naver-mail-ai

# 2) 필요한 부품 설치
py -m pip install -r requirements.txt        # 윈도우
python3 -m pip install -r requirements.txt   # 맥

# 3) 비밀번호 보관 파일 만들기
copy .env.example .env    # 윈도우
cp .env.example .env      # 맥
```

메모장으로 `.env`를 열어 값을 채웁니다.

```ini
NAVER_ID=myshop@naver.com
NAVER_APP_PASSWORD=애플리케이션_비밀번호
AI_PROVIDER=keyword       # keyword / ollama / gemini / codex / openai / anthropic / mock
AI_API_KEY=               # gemini·openai·anthropic 만 필요
# AI_MODEL=               # 비워 두면 기본값
```

> 모델 이름은 바뀔 수 있습니다. 각 회사 문서에서 현재 모델 이름을 확인하세요 (2026년 10월 기준).

## 4. 실행

```bash
py naver_mail_ai.py              # 윈도우 (맥: python3 naver_mail_ai.py)
py naver_mail_ai.py --drafts     # 답장 초안을 drafts 폴더에 txt로도 저장
```

결과 파일: `메일정리_YYYY-MM-DD.csv` (utf-8-sig로 저장해 엑셀에서 한글이 깨지지 않습니다)

### 예시 출력

아래는 예시 메일 3통(예약 문의, 견적서 첨부 메일, 광고)으로 시험한 **예시**입니다.

```text
C:\메일비서> py naver_mail_ai.py --drafts
☀ 2026-10-26 아침 메일 요약 · 안 읽은 메일 3통 (광고 1통)
 [예약] 김하늘 · 토요일 오후 2시 원데이 클래스 4명 예약 문의. 주차 가능 여부도 질문.
 [견적·세금계산서] 가죽나라 이영수 · 가죽나라 10월 원단 견적, 합계 748,000원. 공급가 680,000원 · 부가세 68,000원.
→ 저장: 메일정리_2026-10-26.csv / 답장 초안: drafts 폴더
```

CSV 열: `받은시각, 보낸사람, 주소, 제목, 분류, 요약, 답장초안`

## 돈 안 드는 4가지 방법 (유료 API 없이)

| 방법 (`AI_PROVIDER`) | 비용 | 메일이 밖으로 나가는지 | 품질 | 준비 난이도 |
| --- | --- | --- | --- | --- |
| `keyword` | 0원 | **안 나감** | 낮음 · 낱말 규칙 분류, 요약은 본문 앞 2줄, 답장은 정해진 틀 | ★☆☆ 가장 쉬움 (설정 없음) |
| `ollama` | 0원 (내 PC 전기료) | **안 나감** (내 PC 안에서 처리) | 모델 크기에 따라 다름 · 7b 권장, 작은 모델은 분류 실수가 있음 | ★★☆ 설치 + 모델 내려받기(7b 약 4.7GB) |
| `gemini` | 무료 등급 0원 (하루 사용 한도 있음) | 나감 (구글) · **무료 등급 입력은 구글 제품 개선에 쓰일 수 있음** | 높은 편 | ★☆☆ 키 발급만 |
| `codex` | ChatGPT 구독에 포함된 사용량 (API 요금 아님) | 나감 (OpenAI) | 높은 편 | ★★☆ Node.js + Codex CLI 설치·로그인 |
| `openai` / `anthropic` | 유료 (사용한 만큼) | 나감 | 높음 | ★☆☆ 결제수단 등록 + 키 |

**추천**: 손님 정보가 걱정되시면 **Ollama**(메일이 PC 밖으로 안 나감), 가장 간단하게 시작하려면 **keyword**.

### keyword — AI 없이 낱말 규칙

`.env`에 `AI_PROVIDER=keyword`만 쓰면 됩니다. 제목·본문에 `(광고)·특가 → 광고`, `견적·세금계산서 → 견적·세금계산서`, `예약·클래스·방문 → 예약`, `주문·배송·환불 → 주문`, `문의·궁금·? → 문의` 순서로 검사하고 없으면 `기타`.
코드 위쪽 `RULES`(낱말)와 `TEMPLATES`(답장 틀)를 가게에 맞게 고쳐 쓰세요.

### ollama — 내 PC 안의 AI (윈도우)

1. [ollama.com](https://ollama.com) → **Download** → Windows용 설치 파일을 받아 설치합니다.
2. PowerShell에서 모델을 내려받습니다: `ollama pull qwen2.5:7b` (약 4.7GB). PC가 느리면 `qwen2.5:3b` 또는 `qwen2.5:1.5b`.
3. 확인: `ollama list` 에 모델이 보이고, 브라우저에서 `http://localhost:11434` 를 열면 `Ollama is running` 이 나옵니다.
4. `.env`: `AI_PROVIDER=ollama` (작은 모델이면 `AI_MODEL=qwen2.5:1.5b`)

### gemini — 구글 AI Studio 무료 키

1. [aistudio.google.com/apikey](https://aistudio.google.com/apikey) 에서 구글 계정으로 로그인 → **Create API key**
2. `.env`: `AI_PROVIDER=gemini`, `AI_API_KEY=발급받은_키` (기본 모델 `gemini-3.5-flash-lite`, 2026-10 기준 무료 등급 제공 모델)
3. ⚠️ Gemini API 추가 약관(무료 서비스): *"When you use Unpaid Services … Google uses the content you submit to the Services and any generated responses to provide, improve, and develop Google products and services"*, *"human reviewers may read, annotate, and process your API input and output"*, *"Do not submit sensitive, confidential, or personal information to the Unpaid Services."* → 손님 개인정보가 담긴 메일에는 신중히 쓰세요.

### codex — ChatGPT 구독으로 (Codex CLI)

1. [nodejs.org](https://nodejs.org) 에서 LTS 버전 설치
2. PowerShell: `npm i -g @openai/codex`
3. `codex login` → 브라우저에서 ChatGPT 계정으로 로그인 → `codex login status` 로 확인
4. `.env`: `AI_PROVIDER=codex` (`AI_API_KEY`는 비워 두세요)

- 코드는 `codex exec --sandbox read-only --skip-git-repo-check --ephemeral -` 로 실행합니다. **읽기 전용**이라 Codex가 파일을 고치지 못하고, 부탁 글은 표준입력으로 전달합니다.
- OpenAI 문서: *"When you sign in with an API key, Codex uses standard API pricing instead of included ChatGPT plan credits."* → ChatGPT로 로그인하면 구독에 포함된 사용량을 씁니다(한도가 있음). API 키로 로그인하면 API 요금이 나가니 `codex login status`로 꼭 확인하세요.
- Codex는 ChatGPT Plus·Pro·Business·Edu·Enterprise 요금제에 포함되어 있습니다(2026-10 기준, 한시적으로 Free·Go 체험 제공).
- PowerShell에서 `codex` 실행이 '스크립트를 실행할 수 없습니다'로 막히면 `codex.cmd`로 실행하거나 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 를 고려하세요.

## 5. 예약 실행 (매일 아침 자동)

**윈도우 – 작업 스케줄러**

1. 시작 메뉴에서 **작업 스케줄러** 실행 → 오른쪽 **기본 작업 만들기** → 이름 `메일비서`
2. 트리거 **매일**, 시간 **오전 7:50**
3. 동작 **프로그램 시작** → 프로그램 `py`, 인수 `naver_mail_ai.py --drafts`, 시작 위치 `C:\메일비서`(이 폴더 경로)
4. 그 시간에 PC가 켜져 있어야 합니다.

**맥 – cron**

```bash
crontab -e
# 아래 한 줄 추가 (매일 7시 50분 실행, 기록은 log.txt)
50 7 * * * cd ~/Desktop/naver-mail-ai && python3 naver_mail_ai.py --drafts >> log.txt 2>&1
```

맥이 잠자기 상태면 실행되지 않습니다.

## 6. 시험해 보기 (네이버·AI 없이)

가짜 메일함으로 전체 흐름(접속 → 한글 해독 → AI 응답 처리 → CSV · 초안 저장)을 확인합니다.
인터넷도 비밀번호도 필요 없습니다.

```bash
python3 tests/test_fake.py                # keyword·openai·anthropic·gemini·ollama·codex 모두
python3 tests/test_fake.py keyword        # 한 가지만
python3 tests/test_fake.py ollama-live    # 켜 둔 Ollama로 진짜 AI 분류 (LIVE_MODEL=qwen2.5:1.5b 등)
```

keyword 는 실제로 실행되고, openai·anthropic·gemini·ollama·codex 는 각 회사 형식의 가짜 응답으로 대신합니다.

## 7. 안전 수칙

- **`.env` = 메일함 열쇠 + AI 결제 카드.** 카톡·메일로 보내거나 공유 폴더·깃허브에 올리지 마세요. (`.gitignore`에 포함되어 있습니다)
- 애플리케이션 비밀번호는 **메일함 전체를 여는 열쇠**입니다. 믿을 수 있는 도구에만 넣고, 도구마다 따로 만드세요.
- 이 코드는 **읽기 전용**이며 메일을 **보내지 않습니다**. 답장은 초안을 확인·수정한 뒤 직접 보내세요.
- 메일 본문은 AI 회사 서버로 전달됩니다. 카드·계좌·주민번호가 담긴 메일은 대상에서 빼는 것을 권합니다.
- AI 회사 사이트에서 **월 사용 한도**를 걸어 두세요.
- 더 이상 쓰지 않으면 네이버ID → 보안설정 → 2단계 인증 → 관리에서 **애플리케이션 비밀번호를 삭제**하세요.

## 8. 문제 해결 (자주 나오는 오류)

2026-10-26 윈도우 PC(PowerShell, Python 3.14)에서 실제로 따라 하며 만난 오류입니다.

| 화면에 나온 말 | 원인 | 해결 |
| --- | --- | --- |
| `[AUTH] … Authentication failed. (Please check IMAP/SMTP settings in the webmail)` | IMAP/SMTP 탭이 꺼짐(POP3만 켬), 또는 비밀번호가 틀림 | 환경설정 → POP3/IMAP 설정 → 오른쪽 **IMAP/SMTP 설정** 탭에서 `사용함` 저장 후 1~2분 뒤 재실행. 로그인 비밀번호가 아닌 **애플리케이션 비밀번호**인지, 앞뒤 공백·따옴표가 없는지 확인 |
| `HTTP Error 429: Too Many Requests` | API 크레딧 부족(추정). 메일 1통에 1번 요청이라 과다 호출은 아님 | platform.openai.com 결제 설정에서 결제수단 등록·크레딧 충전 후 몇 분 뒤 재실행. API는 ChatGPT 구독과 별도 과금 |
| `KeyError: 'NAVER_ID'` | `.env`를 못 찾음 (메모장 저장 시 `.env.txt`가 됨) | 다른 이름으로 저장 → 파일 형식 **모든 파일** → 이름 `.env`. 파일 탐색기에서 숨긴 항목·파일 확장명 보기를 켜고 확인 |
| `애플리케이션 이름은 문자,숫자,공백만 가능합니다` | 앱 비밀번호 이름에 하이픈(-) 등 기호 | `mailai`처럼 문자·숫자만 사용 |
| `codex 오류(codex login 확인): … 401 Unauthorized` | Codex CLI에 로그인하지 않음 | `codex login` 후 `codex login status` 확인 |
| `AI 오류: <urlopen error … 10061 …>` 또는 `Connection refused` | Ollama가 꺼져 있음 | Ollama 앱 실행, `http://localhost:11434` 확인 |
| `python` 명령을 찾을 수 없음 (또는 Microsoft Store가 열림) | 설치 때 PATH 추가 안 함 | `py naver_mail_ai.py`로 실행하거나, 파이썬 재설치 시 **Add python.exe to PATH** 체크 |

참고
- 네이버 IMAP/SMTP 설정은 90일 넘게 쓰지 않으면 자동으로 `사용 안 함`으로 바뀝니다.
- POP3는 이 코드에 필요 없습니다.
- AI 호출이 실패해도 분류를 `기타`로 적고 CSV는 저장합니다.
- 애플리케이션 비밀번호 화면은 캡처하지 마세요. 실수로 남았다면 사용 내역에서 삭제 후 재발급하세요.

## 9. 함께 보면 좋은 자료

- 안내서: 『네이버 메일 AI 자동화 왕초보 가이드』 — 부록 「파이썬으로 직접 만들기」, 부록 2 「실제로 따라 해 본 기록」

## 문의

막히는 부분이나 궁금한 점은 이메일로 편하게 문의해 주세요: **[osiki999@gmail.com](mailto:osiki999@gmail.com)**

## 라이선스

[MIT](LICENSE) © 2026 Neosiki
