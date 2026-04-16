# KBO-league

KBO 리그 경기 일정과 경기 자료를 모으고 정리하는 프로젝트입니다.

**Selenium/ChromeDriver 없이** `requests`만 사용하여
KBO 공식 홈페이지에서 데이터를 수집합니다.
2001년부터 최근 시즌까지의 경기 데이터를 포함합니다.

## 설치

```bash
conda create -n KBO-league python=3.12
conda activate KBO-league
pip install -r requirements.txt
```

## 모듈 구조

| 파일 | 역할 |
|------|------|
| `get_kbo.py` | 스케줄 + 경기 데이터 수집 + 변환을 한번에 실행하는 CLI |
| `get_game_schedule.py` | KBO 경기 일정 수집 (월별 CSV, 일별 JSON) |
| `get_game_data.py` | 상세 경기 데이터(타자/투수/스코어보드) 수집 |
| `convert_game_data.py` | 신규 수집 포맷을 기존(2001~2021) 포맷으로 변환 |
| `get.py` | `kbo_data.ini`에 등록된 연도의 전체 데이터를 일괄 로드 |
| `kbo_data.ini` | 연도별 경기 월 목록, 미수집 경기 목록 등 메타 설정 |

## 사용법

### 오늘 경기 일정

```python
import get_game_schedule

# 오늘 경기 일정
games = get_game_schedule.today()
print(games)

# 스코어보드 포함
games = get_game_schedule.today(include_score=True)
print(games[0]["scoreboard"])
```

### 특정 날짜 경기 일정

```python
games = get_game_schedule.by_date("20260328")
```

### 1주일 경기 일정

```python
week = get_game_schedule.by_week("20260328")
for date, games in week.items():
    print(f"{date}: {len(games)}경기")
```

### 스케줄 저장

```python
# 한 달치 스케줄을 CSV로 저장 → data/schedule/2026/2026_03.csv
get_game_schedule.save_month_csv(2026, 3)
```

### 상세 경기 데이터 수집

```python
import get_game_data

# 단일 경기 (sr_id: 0=정규, 1=시범, 3~7=포스트시즌)
data = get_game_data.fetch_game("20260328", "KTLG0")
preseason = get_game_data.fetch_game("20260315", "KTLG0", sr_id=1)

# 날짜 전체
day_data = get_game_data.fetch_date("20260328")

# 한 달치 수집 + 저장 (이미 수집된 경기는 건너뜀)
get_game_data.fetch_month(2026, 4, save=True)

# 저장된 한 달치 데이터 로드
games = get_game_data.load_month(2026, 4)
```

CLI로 단일 경기를 확인할 수도 있습니다:

```bash
# 정규시즌
python get_game_data.py 20260328 KTLG0

# 시범경기
python get_game_data.py 20260315 KTLG0 1
```

### 데이터 포맷 변환

신규 수집 포맷을 기존(2001~2021) 포맷으로 변환하여 `get.game_data()`로
통합 조회할 수 있게 합니다.

```python
import convert_game_data

# 단일 파일 변환 (덮어쓰기)
convert_game_data.convert_file("data/game/2026/2026_04.json")

# 연도 전체 변환
convert_game_data.convert_dir("data/game/2026/")
```

CLI로도 실행할 수 있습니다:

```bash
python convert_game_data.py data/game/2026/2026_04.json
python convert_game_data.py data/game/2026/
```

### 수집 + 변환 한번에

```bash
# 특정 월
python get_kbo.py 2026 4

# 여러 달 (4~10월)
python get_kbo.py 2026 4 10

# 연도 전체 (3~10월)
python get_kbo.py 2026

# 다른 폴더에 저장 (폴더 아래에 data/game/, data/schedule/ 자동 생성)
python get_kbo.py 2026 4 -d /path/to/backup
```

### 저장 위치 변경 (base_dir)

기본값은 프로젝트 루트(`.`)이며, 아래 구조로 저장됩니다:
`{base_dir}/data/game/{year}/`, `{base_dir}/data/schedule/{year}/`.

```python
# 다른 폴더로 수집
get_game_data.fetch_month(2026, 4, save=True, base_dir="/path/to/backup")
get_game_schedule.save_month_csv(2026, 4, base_dir="/path/to/backup")

# 다른 폴더에서 로드
games = get_game_data.load_month(2026, 4, base_dir="/path/to/backup")
```

### 기존 수집 데이터 일괄 읽기

`kbo_data.ini`에 등록된 연도(2001~2021) 데이터를 한 번에 읽어옵니다.
최근 연도(2022~) 데이터를 포함하려면 `kbo_data.ini`의 `[seasons]` 섹션에 추가하세요.

```python
import json
import get

game_data = get.game_data()

with open("game_data.json", "w") as f:
    json.dump(game_data, f, ensure_ascii=False)
```

## 데이터 구조

```
data/
├── game/              # 경기 상세 데이터 (연도/월별 JSON)
│   ├── 2001/
│   │   ├── 2001_04.json
│   │   └── ...
│   ├── ...
│   └── 2026/
│       ├── 2026_03.json
│       └── 2026_04.json
├── schedule/          # 경기 일정
│   ├── 2022/
│   │   ├── 2022_03.csv   # save_month_csv(): 월별 스케줄
│   │   └── ...
│   ├── ...
│   └── 2026/
│       ├── 2026_03.csv
│       ├── 2026_04.csv
│       └── 20260415.json # save_date()/by_date() 캐시 (선택)
└── temp/              # 과거 수집 임시 데이터
```

### 스케줄 CSV 컬럼

| 컬럼 | 설명 |
|------|------|
| `G_ID` | 경기 고유 ID (예: `20260328KTLG0`) |
| `SR_ID` | 시리즈 ID (0=정규, 1=시범, 3~7=포스트) |
| `SEASON_ID` | 시즌 연도 |
| `G_DT` / `G_TM` | 경기 날짜 / 시간 |
| `S_NM` | 구장 이름 |
| `AWAY_ID` / `HOME_ID` | 원정팀 / 홈팀 ID |
| `AWAY_NM` / `HOME_NM` | 원정팀 / 홈팀 이름 |
| `CANCEL_SC_ID` / `CANCEL_SC_NM` | 취소 상태 ID / 이름 |
| `SR_NM` | 시리즈 이름 |

경기가 없는 날짜는 `G_DT`만 채운 빈 줄로 표시됩니다.

### 경기 데이터 포맷

```json
{
  "id": "20260328_KTLG0",
  "contents": {
    "scoreboard": [
      {"팀": "KT", "승패": "승", "1": 6, "2": 0, ..., "R": 11, "H": 18, "E": 0, "B": 6},
      {"팀": "LG", "승패": "패", "1": 0, "2": 0, ..., "R": 7, "H": 12, "E": 0, "B": 8}
    ],
    "ETC_info": {"결승타": "...", "홈런": "...", "심판": ["...", "..."], ...},
    "away_batter": [
      {"포지션": "중", "선수명": "...", "1": "안타", ..., "타수": 4, "안타": 2, "타점": 1, "득점": 1, "타율": 0.3, "팀": "KT"}
    ],
    "home_batter": [...],
    "away_pitcher": [
      {"선수명": "...", "등판": "선발", "결과": "승", ..., "이닝": 7, "삼진": 5, "평균자책점": 3.0, "팀": "KT"}
    ],
    "home_pitcher": [...]
  }
}
```

## 데이터 출처

- [KBO 공식 홈페이지](https://www.koreabaseball.com/)
  - 스코어보드: `/Schedule/ScoreBoard.aspx`
  - 게임센터: `/Schedule/GameCenter/Main.aspx`

## 라이선스

[GPL-3.0](LICENSE)
