"""KBO 경기 일정을 가져오는 모듈

KBO 공식 홈페이지에서 경기 일정을 수집합니다.
Selenium이나 HTML 파싱이 불필요합니다.

스케줄 CSV 컬럼:
    G_ID         경기 고유 ID (예: 20260328KTLG0)
    SR_ID        시리즈 ID (0=정규시즌, 1=시범경기, 3~9=포스트시즌)
    SEASON_ID    시즌 연도
    G_DT         경기 날짜 (YYYYMMDD)
    G_TM         경기 시간 (HH:MM)
    S_NM         구장 이름
    AWAY_ID      원정팀 ID
    HOME_ID      홈팀 ID
    AWAY_NM      원정팀 이름
    HOME_NM      홈팀 이름
    CANCEL_SC_ID 취소 상태 ID (0=정상)
    CANCEL_SC_NM 취소 상태 (정상경기, 우천취소 등)
    SR_NM        시리즈 이름 (정규시즌, 시범경기 등)

    경기가 없는 날짜는 G_DT만 채우고 나머지 컬럼은 빈 값으로 표시합니다.

저장 경로:
    data/schedule/{연도}/{연도}_{월}.csv (예: data/schedule/2026/2026_03.csv)

Example:
    오늘 경기 일정:
        >>> import get_game_schedule
        >>> games = get_game_schedule.today()
        >>> games[0]["G_ID"]
        '20260328KTLG0'

    특정 날짜:
        >>> games = get_game_schedule.by_date("20260328")

    월별 스케줄 CSV 저장:
        >>> get_game_schedule.save_month_csv(2026, 3)

    1주일 스케줄:
        >>> week = get_game_schedule.by_week("20260328")
"""

import json
import os
from datetime import date, timedelta

import requests

API_URL = "https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx",
}

# 정규시즌(0) + 시범(1) + 포스트시즌(3~9)
DEFAULT_SR_ID = "0,1,3,4,5,6,7,8,9"

SCHEDULE_DIR = "data/schedule"  # base_dir 기준 상대 경로


def _schedule_dir(base_dir="."):
    """스케줄 저장 디렉토리 경로를 반환합니다."""
    return os.path.join(base_dir, SCHEDULE_DIR)

SCHEDULE_FIELDS = [
    "G_ID", "SR_ID", "SEASON_ID", "G_DT", "G_TM", "S_NM",
    "AWAY_ID", "HOME_ID", "AWAY_NM", "HOME_NM",
    "CANCEL_SC_ID", "CANCEL_SC_NM",
]

SR_ID_NAMES = {
    0: "정규시즌",
    1: "시범경기",
    3: "와일드카드",
    4: "준플레이오프",
    5: "플레이오프",
    6: "한국시리즈",
    7: "올스타전",
}


def _schedule_path(game_date, base_dir="."):
    """스케줄 저장 경로를 반환합니다."""
    year = game_date[:4]
    return os.path.join(_schedule_dir(base_dir), year, f"{game_date}.json")


def _strip_schedule(games):
    """스케줄 저장용으로 일정 필드만 추출하고 시리즈 이름을 추가합니다."""
    result = []
    for g in games:
        entry = {k: g.get(k, "") for k in SCHEDULE_FIELDS}
        entry["SR_NM"] = SR_ID_NAMES.get(g.get("SR_ID"), "기타")
        result.append(entry)
    return result


def _fetch_from_api(game_date, sr_id=DEFAULT_SR_ID):
    """KBO API에서 경기 목록을 가져옵니다."""
    data = {
        "leId": 1,
        "srId": sr_id,
        "date": game_date,
    }
    resp = requests.post(API_URL, data=data, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    return result.get("game", [])


def by_date(game_date, sr_id=DEFAULT_SR_ID, include_score=False, force_fetch=False, base_dir="."):
    """특정 날짜의 경기 목록을 가져옵니다.

    저장된 스케줄 파일이 있으면 파일에서 읽고, 없으면 API를 호출합니다.

    Args:
        game_date (str): "20260328" 형식의 날짜
        sr_id (str): 시리즈 ID (기본값: 정규+시범+포스트)
        include_score (bool): True이면 각 경기에 scoreboard 요약 추가
        force_fetch (bool): True이면 캐시 무시하고 API 재호출
        base_dir (str): 데이터 루트 디렉토리 (기본값: ".")

    Returns:
        list: 경기 정보 딕셔너리 목록
    """
    path = _schedule_path(game_date, base_dir)

    if not force_fetch and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            games = json.load(f)
    else:
        games = _fetch_from_api(game_date, sr_id=sr_id)

    if include_score:
        for g in games:
            g["scoreboard"] = _extract_scoreboard(g)

    return games


def _extract_scoreboard(game):
    """경기 API 응답에서 스코어보드 요약을 추출합니다."""
    return {
        "away_score": game.get("T_SCORE_CN", ""),
        "home_score": game.get("B_SCORE_CN", ""),
    }


def today(sr_id=DEFAULT_SR_ID, include_score=False):
    """오늘 경기 목록을 가져옵니다."""
    today_str = date.today().strftime("%Y%m%d")
    return by_date(today_str, sr_id=sr_id, include_score=include_score)


def today_legacy():
    """오늘 경기를 기존 KBO-league 포맷으로 변환하여 반환합니다.

    Returns:
        list: [{"gameDate": "20260328", "gameId": "KTLG0", "away": "KT", "home": "LG", ...}, ...]
    """
    games = today()
    return [_to_legacy(g) for g in games]


def by_date_legacy(game_date):
    """특정 날짜 경기를 기존 포맷으로 반환합니다."""
    games = by_date(game_date)
    return [_to_legacy(g) for g in games]


def _to_legacy(g):
    """KBO API 응답을 기존 KBO-league 포맷으로 변환합니다."""
    g_id = g.get("G_ID", "")
    game_date = g_id[:8] if len(g_id) >= 8 else g.get("G_DT", "")
    game_id = g_id[8:] if len(g_id) > 8 else ""

    return {
        "gameDate": game_date,
        "gameId": game_id,
        "away": g.get("AWAY_ID", ""),
        "home": g.get("HOME_ID", ""),
        "away_name": g.get("AWAY_NM", ""),
        "home_name": g.get("HOME_NM", ""),
        "venue": g.get("S_NM", ""),
        "time": g.get("G_TM", ""),
        "away_score": g.get("T_SCORE_CN", ""),
        "home_score": g.get("B_SCORE_CN", ""),
        "state": g.get("CANCEL_SC_NM", ""),
        "finished": g.get("GAME_RESULT_CK", 0) == 1,
        "away_starter": g.get("T_PIT_P_NM", "").strip(),
        "home_starter": g.get("B_PIT_P_NM", "").strip(),
        "win_pitcher": g.get("W_PIT_P_NM", "").strip(),
        "save_pitcher": g.get("SV_PIT_P_NM", "").strip(),
        "lose_pitcher": g.get("L_PIT_P_NM", "").strip(),
    }


def save_date(game_date, sr_id=DEFAULT_SR_ID, base_dir="."):
    """특정 날짜의 스케줄을 API에서 가져와 저장합니다.

    Args:
        game_date (str): "20260328" 형식의 날짜
        base_dir (str): 데이터 루트 디렉토리 (기본값: ".")

    Returns:
        list: 저장된 경기 목록
    """
    games = _fetch_from_api(game_date, sr_id=sr_id)
    stripped = _strip_schedule(games)

    path = _schedule_path(game_date, base_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stripped, f, ensure_ascii=False, indent=2)

    return stripped


def save_month(year, month, sr_id=DEFAULT_SR_ID, base_dir="."):
    """한 달치 스케줄을 저장합니다. 이미 저장된 날짜는 건너뜁니다.

    Args:
        year (int): 연도
        month (int): 월
        base_dir (str): 데이터 루트 디렉토리 (기본값: ".")

    Returns:
        int: 새로 저장한 날짜 수
    """
    import calendar

    _, last_day = calendar.monthrange(year, month)
    saved = 0

    for day in range(1, last_day + 1):
        game_date = f"{year}{month:02d}{day:02d}"
        path = _schedule_path(game_date, base_dir)
        if os.path.exists(path):
            continue
        games = save_date(game_date, sr_id=sr_id, base_dir=base_dir)
        count = len(games)
        if count > 0:
            print(f"  {game_date}: {count}경기 저장")
        saved += 1

    print(f"새로 저장: {saved}일")
    return saved


def save_month_csv(year, month, base_dir="."):
    """스케줄을 API에서 수집하여 월별 CSV로 저장합니다.

    경기 없는 날짜는 G_DT만 채운 빈 줄로 표시합니다.

    Args:
        year (int): 연도
        month (int): 월
        base_dir (str): 데이터 루트 디렉토리 (기본값: ".")

    Returns:
        str: 저장된 CSV 파일 경로
    """
    import calendar
    import csv

    _, last_day = calendar.monthrange(year, month)
    all_rows = []

    for day in range(1, last_day + 1):
        game_date = f"{year}{month:02d}{day:02d}"
        games = _fetch_from_api(game_date)

        if games:
            all_rows.extend(_strip_schedule(games))
        else:
            all_rows.append({"G_DT": game_date})

    dir_path = os.path.join(_schedule_dir(base_dir), str(year))
    os.makedirs(dir_path, exist_ok=True)
    csv_path = os.path.join(dir_path, f"{year}_{month:02d}.csv")
    fieldnames = SCHEDULE_FIELDS + ["SR_NM"]

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    game_count = sum(1 for r in all_rows if r.get("G_ID"))
    no_game_days = sum(1 for r in all_rows if not r.get("G_ID"))
    print(f"저장 완료: {csv_path} ({game_count}경기, 경기없음 {no_game_days}일)")
    return csv_path


def by_week(start_date):
    """특정 날짜부터 7일간의 경기 목록을 반환합니다.

    Args:
        start_date (str): "20260328" 형식의 시작 날짜

    Returns:
        dict: {날짜: 경기 목록} 딕셔너리
    """
    start = date(int(start_date[:4]), int(start_date[4:6]), int(start_date[6:8]))
    result = {}

    for i in range(7):
        d = start + timedelta(days=i)
        game_date = d.strftime("%Y%m%d")
        games = by_date(game_date)
        result[game_date] = games

    return result


if __name__ == "__main__":
    print("=== 오늘 KBO 경기 (API 원본) ===")
    games = today()
    print(f"경기 수: {len(games)}")
    print(json.dumps(games, ensure_ascii=False, indent=2))
