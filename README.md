# KBO-league

KBO 리그 경기 일정과 경기 자료를 모으고 정리하는 프로젝트입니다.

**Selenium/ChromeDriver 없이** `requests` + `BeautifulSoup`만 사용하여
KBO 공식 홈페이지에서 데이터를 수집합니다.
## 설치

```bash
conda create -n KBO-league python=3.12
conda activate KBO-league
pip install -r requirements.txt
```

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

### 상세 경기 데이터 수집

```python
import get_game_data

# 단일 경기
data = get_game_data.fetch_game("20260328", "KTLG0")
print(data["contents"].keys())
# dict_keys(['scoreboard', 'ETC_info', 'away_batter', 'home_batter', 'away_pitcher', 'home_pitcher'])

# 날짜 전체
day_data = get_game_data.fetch_date("20260328")

# 한 달치
month_data = get_game_data.fetch_month(2026, 4)

# 한 달치 수집 + data/game/2026/2026_04.json 저장
month_data = get_game_data.fetch_month(2026, 4, save=True)
```

### 기존 수집 데이터 읽기

2001~2021년 수집된 데이터를 JSON으로 읽을 수 있습니다.

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
├── game/          # 경기 상세 데이터 (연도/월별 JSON)
│   ├── 2001/
│   │   └── 2001_04.json
│   ├── ...
│   └── 2021/
├── schedule/      # 경기 일정 (날짜별 JSON)
└── temp/          # 임시 데이터
```

### 경기 데이터 포맷

```json
{
  "id": "20260328_KTLG0",
  "contents": {
    "scoreboard": [...],
    "ETC_info": {},
    "away_batter": [...],
    "home_batter": [...],
    "away_pitcher": [...],
    "home_pitcher": [...]
  }
}
```

## 데이터 출처

- [KBO 공식 홈페이지](https://www.koreabaseball.com/)
  - 스코어보드: `/Schedule/ScoreBoard.aspx`
  - 게임센터: `/Schedule/GameCenter/Main.aspx`
