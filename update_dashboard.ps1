# 하슬라한의원 대시보드 자동 업데이트
# 매일 아침 실행: 구글 드라이브 xlsx 다운로드 → CSV 갱신 → dashboard.html 재생성

$WorkDir = "C:\Users\하슬라한의원\한의원지표"
$LogFile = "$WorkDir\update_log.txt"
$Claude  = "C:\Users\하슬라한의원\AppData\Roaming\npm\claude.cmd"

Set-Location $WorkDir

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $LogFile "`n===== $timestamp 시작 ====="

$prompt = @"
다음 작업을 순서대로 실행해줘.

1. Google Drive MCP로 파일 ID '1QTOX85QDWBKERfaVIXs071C63XMGaW9n9-rUcDBBDRY' 를 xlsx 형식으로 다운로드해서 'C:\Users\하슬라한의원\한의원지표\data\추나시트.xlsx' 에 저장해줘.
   - mcp__claude_ai_Google_Drive__download_file_content 도구 사용
   - exportMimeType: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
   - content 필드(base64)를 디코딩해서 파일로 저장

2. PowerShell로 실행: python 'C:\Users\하슬라한의원\한의원지표\read_chuna.py'

3. PowerShell로 실행: python 'C:\Users\하슬라한의원\한의원지표\read_okchart.py'

4. PowerShell로 실행: python 'C:\Users\하슬라한의원\한의원지표\read_retention.py'

5. PowerShell로 실행: python 'C:\Users\하슬라한의원\한의원지표\generate_dashboard.py'

오류 없이 완료되면 "완료"라고만 출력해줘.
"@

Write-Host "대시보드 업데이트 시작..."
& $Claude --print $prompt --allowedTools "mcp__claude_ai_Google_Drive__download_file_content,PowerShell,Write" 2>&1 | Tee-Object -Append $LogFile

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $LogFile "===== $timestamp 완료 ====="
Write-Host "완료."

# ── GitHub Pages 자동 배포 ─────────────────────────────
Write-Host "GitHub Pages 배포 중..."
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
Set-Location $WorkDir
git add index.html
$today = Get-Date -Format "yyyy-MM-dd"
git commit -m "Auto update: $today" 2>&1 | Out-Null
git push origin main 2>&1 | Tee-Object -Append $LogFile
Write-Host "배포 완료: https://sjc0310-a11y.github.io/haslla-dashboard/" -ForegroundColor Green
Add-Content $LogFile "GitHub Pages 배포 완료: $today"
