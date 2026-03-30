"""KBO 경기 일정을 가져오는 모듈

KBO 공식 JSON API를 사용하여 경기 일정과 결과를 수집합니다.
Selenium 불필요, HTML 파싱 불필요 — 순수 JSON API 호출만 사용합니다.

Example:
    오늘 경기 일정:
        >>> import get_game_schedule
        >>> games = get_game_schedule.today()
        >>> games[0]["G_ID"]
        '20260328KTLG0'

    특정 날짜:
        >>> games = get_game_schedule.by_date("20260328")

    기존 포맷 호환:
        >>> schedule = get_game_schedule.today_legacy()
        >>> schedule[0]
        {'gameDate': '20260328', 'gameId': 'KTLG0', 'away': 'KT', 'home': 'LG', ...}
"""

from datetime import date

import requests

API_URL = "https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx",
}

# 정규시즌(0) + 시범(1) + 포스트시즌(3~9)
DEFAULT_SR_ID = "0,1,3,4,5,6,7,8,9"


def by_date(game_date, sr_id=DEFAULT_SR_ID, include_score=False):
    """특정 날짜의 경기 목록을 KBO API에서 가져옵니다.

    Args:
        game_date (str): "20260328" 형식의 날짜
        sr_id (str): 시리즈 ID (기본값: 정규+시범+포스트)
        include_score (bool): True이면 각 경기에 scoreboard 요약 추가

    Returns:
        list: 경기 정보 딕셔너리 목록 (KBO API 원본 포맷)
    """
    data = {
        "leId": 1,
        "srId": sr_id,
        "date": game_date,
    }
    resp = requests.post(API_URL, data=data, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    games = result.get("game", [])

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


if __name__ == "__main__":
    import json

    print("=== 오늘 KBO 경기 (API 원본) ===")
    games = today()
    print(f"경기 수: {len(games)}")
    print(json.dumps(games, ensure_ascii=False, indent=2))
