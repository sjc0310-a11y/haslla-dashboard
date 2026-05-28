# -*- coding: utf-8 -*-
"""선주천 탭에 '만성 디스크 표준 프로토콜' 12주 예시 데이터를 주입.

사용법 (한의원 PC):
    1on1.bat 종료 → python seed_demo_disc.py → 1on1.bat 재실행

멱등 — 같은 ID 데이터가 이미 있으면 덮어쓰고, 다른 데이터는 보존.
실행 전 data/1on1.json.bak.seed 백업이 자동 생성됨.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "1on1.json"

PROJECT = {
    "id":         "p_demo_disc01",
    "name":       "만성 디스크 환자 표준 프로토콜 정착",
    "priority":   "High",
    "status":     "Done",
    "mood":       "😎",
    "created":    "2026-03-05",
    "start_date": "2026-03-05",
    "end_date":   "2026-05-28",
    "goal":       "부원장 4명 모두 만성 디스크(2주 이상 통증) 환자에게 동일한 평가·치료·교육 흐름을 적용",
    "metric":     "4주 재진율 65→79% (목표 80%) · 체크리스트 5항목 기록률 0→87% (목표 90%)",
    "memo":       "12주 종료 후 다음 사이클은 '김한중 부원장 진료 패턴 코칭'으로 이어짐",
    "tactics": [
        {"id":"t_demo_w01","week":1, "text":"최근 3개월 만성 디스크 차트 50건 검토",           "done":True,"done_date":"2026-03-11"},
        {"id":"t_demo_w02","week":2, "text":"부원장 4명 미니 인터뷰 (현재 진료 방식 청취)",     "done":True,"done_date":"2026-03-18"},
        {"id":"t_demo_w03","week":3, "text":"NICE 2020·대한침구학회 가이드라인 정리 (ODI·NPRS)","done":True,"done_date":"2026-03-25"},
        {"id":"t_demo_w04","week":4, "text":"프로토콜 v0.1 작성 — 평가 3 + 치료 4 + 교육지 2",  "done":True,"done_date":"2026-04-01"},
        {"id":"t_demo_w05","week":5, "text":"방민준 부원장 1주 베타 테스트",                    "done":True,"done_date":"2026-04-08"},
        {"id":"t_demo_w06","week":6, "text":"베타 피드백 수렴 → v0.2 수정",                     "done":True,"done_date":"2026-04-15"},
        {"id":"t_demo_w07","week":7, "text":"메디스트림에 OK차트 템플릿 5칸 추가 요청",          "done":True,"done_date":"2026-04-22"},
        {"id":"t_demo_w08","week":8, "text":"부원장 4명 시연 모임 + 의견 수렴",                  "done":True,"done_date":"2026-04-29"},
        {"id":"t_demo_w09","week":9, "text":"v1.0 확정 + 인쇄물·환자 교육지 배포",               "done":True,"done_date":"2026-05-06"},
        {"id":"t_demo_w10","week":10,"text":"전체 도입, 일일 차트 모니터링 시작",                "done":True,"done_date":"2026-05-13"},
        {"id":"t_demo_w11","week":11,"text":"2주차 점검 — 김한중 부원장 1:1 코칭 추가",          "done":True,"done_date":"2026-05-20"},
        {"id":"t_demo_w12","week":12,"text":"측정 지표 비교 → 결과 평가·Done 처리",             "done":True,"done_date":"2026-05-27"},
    ],
    "learnings": [
        {"date":"2026-03-15","text":"차트 50건 중 ODI 측정 90% 누락. 다 구두로만 통증 평가 중", "meeting_id":None},
        {"date":"2026-03-22","text":"부원장별 만성 디스크 평균 진료시간 2배 차이 (방민준 15분 / 김한중 7분)", "meeting_id":None},
        {"date":"2026-04-05","text":"NICE 가이드라인 핵심: '보존치료 6주 + 자가관리 교육'. 우리 한의원은 교육자료 0건", "meeting_id":"m_demo_disc_apr"},
        {"date":"2026-04-19","text":"방민준 베타 1주차 — 환자 5명 만족도 4.8/5.0. 진료시간 1분 늘었지만 환자 이해도 급상승", "meeting_id":None},
        {"date":"2026-04-26","text":"OK차트 본사(메디스트림) 응대 의외로 빠름 (1주 내 처리). 다음 프로젝트도 같이 쓸 만함", "meeting_id":"m_demo_disc_may"},
        {"date":"2026-05-10","text":"김한중 부원장 우려: '구조화하면 진료 흐름 끊긴다' → 환자 카드 1장으로 흐름 시각화 하니 수용", "meeting_id":None},
        {"date":"2026-05-25","text":"12주 결과: 재진율 65→79%, 기록률 0→87%. 김한중만 60% — 다음 사이클 별도 코칭 필요", "meeting_id":"m_demo_disc_may28"},
    ],
}

MEETING_APR = {
    "id": "m_demo_disc_apr",
    "date": "2026-04-02",
    "month": "2026-04",
    "done": True,
    "mood": "😀",
    "topic_projects": ["p_demo_disc01"],
    "reflect": (
        "차트 50건 검토하면서 충격적인 발견 — 만성 디스크 환자 90%가 ODI 측정 누락. "
        "다 \"통증 어떠세요?\" 구두로만 묻고 있었다. 부원장 인터뷰에서도 4명 다 완전히 다른 "
        "진료 패턴. 방민준은 침+추나 위주 15분, 김한중은 침만 7분. 평균 진료시간 2배 차이.\n\n"
        "가이드라인 정리는 NICE 2020 + 대한침구학회 자료로 했고, \"보존치료 6주 + 자가관리 "
        "교육\"이 핵심이라는 게 가장 큰 인사이트. 우리는 치료는 하는데 환자 교육자료가 전혀 없음.\n\n"
        "프로토콜 v0.1 초안 완료. 평가 3개(ODI·NPRS·SLR), 치료 4종(침·추나·부항·약침), "
        "교육지 2장(자가운동·생활관리)."
    ),
    "next": (
        "- W5에 방민준 부원장과 1주 베타 테스트 (본인이 적극적이라 시작점으로 좋음)\n"
        "- W6에 베타 피드백 → v0.2 수정\n"
        "- W7에 OK차트 템플릿 5칸 추가를 본사에 요청\n"
        "- 김한중 부원장은 W8 모임 자리에서 자연스럽게 합류시키기 (지금 직접 설득은 부담)"
    ),
    "support": [
        {"id":"s_demo_apr_01","type":"Help",     "need":"OK차트 템플릿 추가 — 메디스트림 본사 누구에게 연락? 원장님이 직접?","reviewed":True, "project_id":"p_demo_disc01"},
        {"id":"s_demo_apr_02","type":"Alignment","need":"김한중 부원장 설득 전략 — 진료시간 늘리는 거 어떻게 부드럽게?",       "reviewed":True, "project_id":"p_demo_disc01"},
        {"id":"s_demo_apr_03","type":"Decision", "need":"추나 환자 늘면서 진료실 회전 빡빡 — 진료실 운영 조정?",               "reviewed":False,"project_id":None},
    ],
}

MEETING_MAY = {
    "id": "m_demo_disc_may",
    "date": "2026-04-30",
    "month": "2026-04",
    "done": True,
    "mood": "😎",
    "topic_projects": ["p_demo_disc01"],
    "reflect": (
        "베타 결과 매우 긍정적. 방민준 부원장 1주 베타에서 환자 5명 만족도 4.8/5.0. "
        "진료시간은 1분 늘었지만 환자 이해도가 눈에 띄게 좋아짐.\n\n"
        "v0.2 수정은 방민준 의견(교육지가 너무 길다 → 1장으로 축약) 반영해서 완료. "
        "메디스트림 본사 응대가 의외로 빨랐음 — 1주 내에 OK차트 템플릿 5칸 추가 완료.\n\n"
        "W8 모임에서 김한중 부원장이 우려 표시했지만 (\"진료 흐름 끊길 것 같다\"), "
        "방민준 부원장이 실제 체감을 공유하니 분위기 바뀜. 이문환 부원장이 적극 동조 — "
        "본인도 표준화에 관심 많았다고 함.\n\n"
        "측정 지표: 재진율 65→71%, 기록률 0→38% (방민준 베타분만 기록됨). 절반 정도 진척."
    ),
    "next": (
        "- W9에 v1.0 확정 + 인쇄물 배포\n"
        "- W10에 전체 도입 시작 + 일일 모니터링\n"
        "- W11에 2주차 점검 미팅 — 김한중 부원장 우려 부분 별도 1:1 코칭\n"
        "- W12에 측정 지표 최종 비교 → Done 처리할지 다음 12주로 연장할지 결정"
    ),
    "support": [
        {"id":"s_demo_may_01","type":"Decision","need":"인쇄 비용 처리 방식 — 한 번에? 매월?",                "reviewed":True,"project_id":"p_demo_disc01"},
        {"id":"s_demo_may_02","type":"Help",    "need":"환자 교육 영상 제작 외주 가능? 자가운동 시퀀스 2분짜리","reviewed":True,"project_id":"p_demo_disc01"},
    ],
}

MEETING_MAY28 = {
    "id": "m_demo_disc_may28",
    "date": "2026-05-28",
    "month": "2026-05",
    "done": True,
    "mood": "😎",
    "topic_projects": ["p_demo_disc01"],
    "reflect": (
        "최종 결과 — 거의 모든 목표 달성.\n"
        "- 4주 재진율 65% → 79% (목표 80%, 거의 도달)\n"
        "- 체크리스트 기록률 0% → 87% (목표 90%)\n\n"
        "부원장별 편차는 여전: 본인·이문환·방민준 90%+, 김한중만 60%. W11 코칭에서 핵심 발견 — "
        "\"구조화하면 흐름 끊긴다\" 우려가 본질. 환자 카드 1장으로 진료 흐름 시각화 해주니 수용. "
        "다음 사이클에서 김한중 부원장 별도 케어 필요.\n\n"
        "의외의 효과: 부원장 간 케이스 공유 문화 생김. 같은 평가 척도(ODI)를 쓰니까 "
        "\"이 환자 ODI 32였는데 4주 후 18로 떨어졌어요\" 같은 대화가 자연스럽게 진료실에서 오감."
    ),
    "next": (
        "이 프로젝트는 Done 처리 (W12 사이클 완료). 다음 12주 후보:\n"
        "1. 환자 교육 영상 시리즈 제작 — 만성 디스크 외 4개 카테고리(거북목·어깨·무릎·다이어트)로 확장\n"
        "2. 김한중 부원장 진료 패턴 코칭 — 별도 1on1 프로젝트로\n\n"
        "1번이 임팩트 크고, 2번은 사람 변화라 시간 더 걸림. 2번을 먼저 시작하는 게 다음 12주에 어울림."
    ),
    "support": [
        {"id":"s_demo_may28_01","type":"Decision","need":"다음 12주 프로젝트 확정 — 김한중 코칭으로 갈지 영상 제작으로 갈지","reviewed":False,"project_id":None},
    ],
}

MEETINGS = [MEETING_APR, MEETING_MAY, MEETING_MAY28]
DOCTOR   = "선주천"


def main():
    if not DATA.exists():
        raise SystemExit(f"data 파일 없음: {DATA}\n1on1.bat 한 번 실행 후 다시 시도하세요.")

    raw = json.loads(DATA.read_text(encoding="utf-8"))
    raw.setdefault("notes", {})
    raw.setdefault("projects", {})
    raw["notes"].setdefault(DOCTOR, [])
    raw["projects"].setdefault(DOCTOR, [])

    # 백업
    bak = DATA.with_suffix(".json.bak.seed")
    shutil.copy2(DATA, bak)
    print(f"[backup] {bak.name} 생성")

    # 중복 ID 제거 후 추가 (멱등)
    seed_meeting_ids = {m["id"] for m in MEETINGS}
    raw["projects"][DOCTOR] = [p for p in raw["projects"][DOCTOR] if p.get("id") != PROJECT["id"]]
    raw["notes"][DOCTOR]    = [m for m in raw["notes"][DOCTOR]    if m.get("id") not in seed_meeting_ids]

    raw["projects"][DOCTOR].append(PROJECT)
    raw["notes"][DOCTOR].extend(MEETINGS)
    raw["notes"][DOCTOR].sort(key=lambda m: m.get("date", ""), reverse=True)

    DATA.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {DOCTOR} 탭에 '만성 디스크 표준 프로토콜' 예시 추가됨")
    print(f"      · 프로젝트 1, 면담 3, 인사이트 7, 주간 액션 12, Support 6")
    print(f"      · 1on1.bat 재실행 후 {DOCTOR} 탭에서 확인하세요")


if __name__ == "__main__":
    main()
