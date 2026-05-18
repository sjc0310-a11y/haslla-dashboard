# 한의원 경영 대시보드 (하슬라한의원 기반)

매주 자동 갱신되는 한의원 경영 대시보드. 매출·재진율·초진/재초진·추나
현황을 GitHub Pages로 배포해서 어디서든 볼 수 있습니다.

**데모:** https://sjc0310-a11y.github.io/haslla-dashboard/

---

## 우리 한의원에 그대로 적용하기

→ **[SETUP_PROMPT.md](SETUP_PROMPT.md)** 의 프롬프트를 Claude Code/Cursor에
복사·붙여넣기 하면 AI가 단계별로 안내합니다.

전제 조건:
- 한방 **OK차트** 사용 중 (SQL Server)
- Windows PC + Python 3
- GitHub 계정
- (선택) Notion 계정 — 주간 회고용

---

## 무엇이 나오는가

- **개인 뷰** — 원장별로 본인 KPI(건보·자보·비급여·재진율·추나) 한눈에
- **주간 현황 KPI 카드** — 건보·자보·비급여·재진율·신환 (홈 화면)
- **원장별 매출** — 표 + 도넛 차트, 매출 비율 % 표시
- **월별 원장별 매출 추이** — 최근 3개월
- **원장별 재진/삼진률** — 신호등 색상(목표 80%/70%) + 12주 추이 라인
- **재진 코호트 환자 명단** — 표 셀 클릭 시 환자명 + 내원 횟수 모달
- **원장별 추나 현황** — 건보추나 목표 50건/주 신호등(초록/노랑/빨강)
- **일별 추나 상세** — 출근일(0) vs 비번(−) 구분
- **월별 건보추나** — 표 + 차트 (인센티브 집계용)
- **월별 원장별 초진·재초진** — TA초진 / 건보초진 / (초진+재초진 stacked) 3개 차트
- **노션 주간 회고 동기화** — 노션 DB에서 작성, 페이지에서 원장 탭별로 열람

---

## 자동화

- 매주 일요일 18:00 — Windows Task Scheduler가 `update_dashboard.bat` 실행
  - OK차트 SQL 직접 쿼리 (Receipt / Detail / Customer)
  - 추나/재진/노션 회고 동기화
  - `index.html` 재생성
  - git commit + push → GitHub Pages 자동 재배포
- PC가 꺼져있어 일요일에 못 돌았으면 다음 부팅 후 1시간 안에 자동 재실행
  (`StartWhenAvailable = true`)
- 페이지 헤더의 **🔄 지금 업데이트** 버튼 — 한의원 PC에서 즉시 갱신
  (Windows `haslla://` protocol 사용)

---

## 데이터 흐름

```
OK차트 SQL Server
  ├─ Receipt 테이블 ──┐
  ├─ Detail 테이블 ───┤── read_okchart.py
  └─ Customer 테이블 ─┘     read_retention.py
                            (CSV/JSON 저장)
                                  │
구글 시트 (추나) ── read_chuna.py ─┤
                                  │
노션 DB (회고) ── read_retro_from_notion.py
                                  │
                                  ▼
                       generate_dashboard.py
                                  │
                                  ▼
                            index.html
                                  │
                            git push
                                  ▼
                        GitHub Pages 배포
```

---

## 파일 구조

```
한의원지표/
├── generate_dashboard.py          # 메인 — 데이터 로드 + HTML 생성
├── read_okchart.py                # OK차트 SQL → 원장별현황.csv
├── read_chuna.py                  # 구글 시트 → 추나현황.csv
├── read_retention.py              # OK차트 SQL → retention.csv + 환자명단.json
├── read_retro_from_notion.py      # 노션 DB → retro.json
├── update_dashboard.bat           # 매주 자동 실행 (모든 read_*.py + generate + push)
├── index.html                     # GitHub Pages가 배포하는 결과물
├── data/                          # CSV/JSON 캐시 (gitignored)
├── README.md
└── SETUP_PROMPT.md                # 다른 한의원이 적용할 때 쓰는 AI 프롬프트
```

---

## 한의원 명단 변경

`generate_dashboard.py` 상단:

```python
DOCTORS         = ["노왕식", "이문환", "방민준"]              # 추나 차트 대상
ACTIVE_DOCTORS  = ["노왕식", "이문환", "방민준", "김한중"]   # 개인 뷰 + 회고 탭
EXCLUDE_FROM_STATS = ["선주천", "배용빈"]                    # 통계 제외 (대표원장·퇴사자)

DOC_COLORS = {
    "노왕식": "#3b82f6",
    ...
}
```

원장 입/퇴사 시 위 네 변수만 손보면 끝. 자세한 사용 시나리오는 SETUP_PROMPT.md 참고.

---

## 라이선스

MIT
