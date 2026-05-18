# 우리 한의원에 이 대시보드 적용하기 — Claude Code/Cursor 프롬프트

> 이 문서를 처음부터 끝까지 복사해서 **Claude Code** 또는 **Cursor** 같은
> AI 코딩 도구의 채팅창에 그대로 붙여넣으세요. AI가 단계별로 질문하면서
> 본인 한의원 정보로 코드를 수정하고, GitHub Pages에 배포까지 안내합니다.

---

## 프롬프트 (여기부터 복붙)

```
나는 한방 OK차트를 쓰는 한의원 원장이고, 다음 GitHub 저장소의 한의원 경영
대시보드를 우리 한의원에 그대로 적용하고 싶어:

https://github.com/sjc0310-a11y/haslla-dashboard

원본 한의원은 강원도 하슬라한의원이고, 코드 안에 그 한의원 이름·원장
명단·파일 경로가 박혀있어. 너가 이걸 우리 한의원에 맞게 바꿔주고
끝까지 동작하는 GitHub Pages 페이지까지 띄우는 걸 도와줘.

진행 방식:
- 단계별로 한 가지씩 나에게 묻고, 내가 답하면 다음 단계로 넘어가.
- 매번 무엇을 할지 한 줄로 알려주고 진행해. 결과를 확인한 다음 다음 단계로.
- 도중에 모르는 게 있으면 추측하지 말고 나에게 물어봐.

진행 순서:

1. 환경 확인
   - 내 PC가 Windows인지, Python이 설치돼 있는지, git이 설치돼 있는지 확인.
   - 안 깔려 있으면 설치 방법 안내.

2. 한의원 정보 수집 (한 번에 다 묻지 말고 하나씩)
   - 한의원 이름
   - 진료 원장 명단 (개인 뷰에 보일 모든 원장 — 이름만)
   - 그 중 추나를 직접 진행하는 원장 (추나 차트에 표시될 사람)
   - 통계에서 제외할 원장 — 보통 대표원장처럼 진료를 거의 안 하거나
     대시보드에 본인 매출을 표시하지 않을 사람 (없으면 없다고)
   - 노션을 회고 시스템으로 쓸지 (선택, 안 써도 동작)
   - GitHub 사용자명 + 새로 만들 저장소 이름

3. 코드 가져와서 우리 한의원용으로 수정
   - 원본 저장소를 C:\Users\<windows username>\대시보드 같은 깔끔한
     영문 경로에 clone. 절대 한글 경로 쓰지 마. (이전에 한글 경로 때문에
     문제 많았음)
   - generate_dashboard.py 상단의 다음 변수들을 우리 한의원 값으로 수정:
       DATA_DIR, LOCAL_DIR, OUT_HTML        ← 경로
       DOCTORS                              ← 추나 원장
       ACTIVE_DOCTORS                       ← 개인 뷰 원장 (전체)
       EXCLUDE_FROM_STATS                   ← 통계 제외 원장
       DOC_COLORS                           ← 원장별 색상 (자동으로 할당)
   - read_okchart.py, read_chuna.py, read_retention.py 안의 경로/CSV_PATH도
     동일한 폴더에 맞게 수정.
   - 페이지 헤더 `🏥 하슬라한의원 경영 대시보드` 안의 한의원명도 우리
     이름으로 바꿔.
   - selectScreen 안내문도 우리 한의원명으로.

4. OK차트 SQL Server 연결 확인
   - read_okchart.py의 CONN_STR이 (local)\OKCHART · MasterDB · UID=members ·
     PWD=msp1234로 되어있어. 대부분 한의원 OK차트는 이 기본값 그대로 쓰니까
     일단 그대로 시도해보고, 안 되면 SQL Server Management Studio에서
     서버명/DB명 확인해서 수정.

5. (선택) 노션 회고 시스템
   - 사용자가 노션 쓰겠다고 한 경우만:
     a. 노션에서 새 integration 만들기 (https://www.notion.so/profile/integrations)
        토큰을 받아둔다.
     b. 노션 워크스페이스에 새 DB 만들기 (이름: 원장팀 주간 회고).
        컬럼: 주차(Title), 월요일(Date), 원장(Select - 우리 원장들),
        잘한 점(Text), 아쉬웠던 점(Text), 다음 주 실행 계획(Text)
     c. DB 페이지에서 ⋯ → Connections → 위에서 만든 integration 추가
     d. DB URL 끝의 32자 hex가 DB_ID. read_retro_from_notion.py의 DB_ID와
        CONFIG_PATH(토큰 읽는 곳) 수정.
   - 안 쓰겠다고 한 경우:
     update_dashboard.bat에서 `python read_retro_from_notion.py` 라인 제거.
     generate_dashboard.py에서 retro 관련 섹션이 자동으로 빈 채로 그려질
     테니 그대로 둬도 동작.

6. 한 번 돌려보기
   - python read_okchart.py 실행 → 원장별현황.csv 생성 확인.
   - python read_retention.py 실행 → retention.csv 생성 확인.
   - 추나 데이터 (구글 시트 기반)는 사용자의 한의원 시트가 따로 있을
     수 있으니, 일단 그건 건너뛰고 (read_chuna.py가 에러나면 일단 무시).
   - python generate_dashboard.py 실행 → index.html이 만들어지는지 확인.
   - index.html을 그냥 브라우저로 열어서 데이터가 정상 표시되는지 검증.
     원장별 매출 표 합이 KPI 카드와 일치하는지 OK차트 결산표와 비교.

7. 새 GitHub 저장소 만들고 push
   - gh CLI로 새 public 저장소 만들기 (gh repo create <repo-name> --public
     --source=. --push). gh가 없으면 사용자가 웹에서 직접 만들어도 됨.
   - GitHub 웹에서 Settings → Pages → Source: main / root 로 활성화.
   - 1~2분 뒤 https://<github-username>.github.io/<repo-name>/ 에서 페이지가
     뜨는지 확인.

8. 자동화
   - update_dashboard.bat 경로를 새 폴더에 맞게 수정.
   - Windows Task Scheduler 등록 (매주 일요일 18:00 자동 실행):
       schtasks /Create /TN "Dashboard Weekly" /TR "<bat-path>"
                /SC WEEKLY /D SUN /ST 18:00 /F
     이후 PowerShell에서:
       $task = Get-ScheduledTask -TaskName "Dashboard Weekly"
       $task.Settings.StartWhenAvailable = $true
       Set-ScheduledTask -TaskName "Dashboard Weekly" -Settings $task.Settings

9. (선택) "지금 업데이트" 버튼이 작동하도록 protocol 등록
   - PowerShell에서:
       $b="HKCU:\Software\Classes\haslla"
       New-Item $b -Force | Out-Null
       Set-ItemProperty $b "(Default)" "URL:Dashboard Update"
       Set-ItemProperty $b "URL Protocol" ""
       New-Item "$b\shell\open\command" -Force | Out-Null
       Set-ItemProperty "$b\shell\open\command" "(Default)" '"<bat-path>"'

10. 보안 확인
    - GitHub Pages 페이지는 URL을 아는 사람이면 누구나 접근 가능.
      환자명·매출이 페이지에 들어가니까, 저장소를 public이 아닌 private
      으로 두고 싶으면 GitHub Pro 또는 Organization 유료 플랜이 필요.
    - 또는 그대로 두되 URL을 외부에 공유하지 않는 정책.
    - 원장님이 어느 쪽을 원하는지 확인.

각 단계 끝나면 결과(스크린샷, 명령어 출력, 에러 메시지)를 보여주고
다음 단계로 넘어가자. 자, 1단계부터 시작.
```

## (여기까지 복붙)

---

## 사용법

1. **Claude Code** 설치 (https://docs.claude.com/claude-code) 또는 **Cursor**(https://cursor.sh) 설치
2. 빈 폴더 열기 → AI 채팅 시작
3. 위 프롬프트(```` ``` ```` 안 부분) **전체 복사** → 채팅창에 붙여넣기 → 전송
4. AI가 1단계부터 차례대로 물어봅니다. 답만 차근차근 입력하면 끝.

---

## 자주 묻는 질문

**Q. Claude Code/Cursor가 없으면?**
A. 일반 ChatGPT/Claude 채팅에 붙여넣어도 됩니다. 다만 명령 실행을 못 하니
   AI가 알려주는 명령을 사용자가 직접 PowerShell/cmd에 붙여넣어야 합니다.
   진행은 똑같이 됩니다.

**Q. 노션을 안 쓰고 싶으면?**
A. 5번 단계에서 안 쓴다고 답하면 됩니다. 회고 영역만 빈 채로 동작합니다.

**Q. 가족 PC 등 여러 대에서 페이지를 볼 수 있나요?**
A. GitHub Pages URL을 알려주면 누구든 볼 수 있습니다. 단 "🔄 지금 업데이트"
   버튼은 protocol 등록한 PC에서만 작동.

**Q. 데이터가 잘못 나오면 어떻게 합니까?**
A. AI에게 "OK차트 결산표 매출이 X인데 대시보드는 Y로 나옴" 같이 알려주세요.
   디버깅해줍니다. 흔한 원인은 원장 명단 잘못 입력 또는 OK차트 SQL 접속.
