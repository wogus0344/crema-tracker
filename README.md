# 나스닥 크레마 지수 안드로이드 모바일 웹앱 & 매일 07:00 KST 자동 누적 패키지

## 1. 구성 파일 안내
- `index.html`: 안드로이드(갤럭시 S24 울트라 등) 모바일 화면에 최적화된 **QQQ · QTY(QLD) · TQQQ 최근 6개월 일봉 + 크레마 지수 + 6대 세부 지표 일별 드래그 대시보드**
- `update_crema_data.py`: 매일 한국시간 07:00에 Yahoo Finance(`yfinance`)와 CNN 공포·탐욕 지수를 수집해 `index.html` 내부 데이터를 자동 갱신하는 파이썬 스크립트
- `.github/workflows/daily_crema_update.yml`: PC나 휴대폰이 꺼져 있어도 깃허브 클라우드 서버가 매일 07:00 KST에 위 파이썬 스크립트를 자동 실행하고 저장하는 스케줄러 설정 파일
- `manifest.json`: 갤럭시 홈 화면에 추가했을 때 주소창 없는 전용 앱 화면으로 실행해 주는 설정 파일

## 2. 3분 만에 깃허브(GitHub Pages)에 올리고 휴대폰에서 보는 법
1. [GitHub](https://github.com/)에서 새 저장소(Repository, 예: `crema-tracker`)를 **Public**으로 생성합니다.
2. 본 압축파일(`crema_github_pages_bundle.zip`)의 압축을 푼 뒤, 내부 파일과 폴더(`.github/workflows/daily_crema_update.yml`, `index.html`, `update_crema_data.py`, `manifest.json`)를 그대로 업로드(Commit)합니다.
3. 저장소 상단 **Settings → Pages** 메뉴로 이동하여 **Build and deployment → Source**를 `Deploy from a branch`, 브랜치를 `main` (폴더 `/ (root)`)으로 선택 후 **Save**를 누릅니다.
4. 약 1분 뒤 생성되는 `https://<본인깃허브아이디>.github.io/crema-tracker/` 주소를 갤럭시 **Chrome** 또는 **삼성 인터넷**으로 엽니다.
5. 브라우저 우측 상단(또는 하단) 메뉴에서 **[홈 화면에 추가]**를 누르면 휴대폰 바탕화면에 **크레마지수** 앱 아이콘이 생성되어 언제든 터치 한 번으로 일별 데이터를 조회할 수 있습니다.
