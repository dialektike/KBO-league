# KBO-league

KBO 리그 경기 일정과 경기 자료를 모으고 정리하는 프로젝트입니다.

**Selenium/ChromeDriver 없이** `requests`만 사용하여
KBO 공식 JSON API에서 데이터를 수집합니다.

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

# 단일 경기
data = get_game_data.fetch_game("20260328", "KTLG0")

# 날짜 전체
day_data = get_game_data.fetch_date("20260328")

# 한 달치 수집 + 저장
get_game_data.fetch_month(2026, 4, save=True)
```

### 데이터 포맷 변환

수집한 데이터를 기존(2001~2021) 포맷으로 변환합니다.

```python
import convert_game_data

# 단일 파일 변환 (덮어쓰기)
convert_game_data.convert_file("data/game/2026/2026_04.json")

# 연도 전체 변환
convert_game_data.convert_dir("data/game/2026/")
```

### 수집 + 변환 한번에

```bash
# 특정 월
python get_kbo.py 2026 4

# 여러 달 (4~10월)
python get_kbo.py 2026 4 10

# 연도 전체 (3~10월)
python get_kbo.py 2026
```

### 기존 수집 데이터 읽기

2001~2026년 수집된 데이터를 JSON으로 읽을 수 있습니다.

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
│   └── 2026/
├── schedule/      # 경기 일정 (월별 CSV)
│   ├── 2025/
│   └── 2026/
└── temp/          # 과거 수집 임시 데이터
```

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
