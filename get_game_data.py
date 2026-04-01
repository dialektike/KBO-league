"""KBO 게임센터에서 상세 경기 데이터를 수집하는 모듈

KBO 공식 JSON API를 사용하여 타자/투수/기타 기록을 수집합니다.
Selenium 불필요, HTML 파싱 불필요.

API 엔드포인트:
    - GetKboGameList: 경기 목록
    - GetBoxScoreScroll: 상세 박스스코어 (타자, 투수, 기타 기록)

Example:
    단일 경기:
        >>> import get_game_data
        >>> data = get_game_data.fetch_game("20260328", "KTLG0")

    날짜 전체:
        >>> games = get_game_data.fetch_date("20260328")
"""

import json
import time

import requests

import get_game_schedule

BOXSCORE_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetBoxScoreScroll"
SCOREBOARD_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetScoreBoardScroll"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx",
}


def _extract_text(rows):
    """KBO API의 rows 구조에서 Text 값만 추출하여 리스트로 반환합니다."""
    result = []
    for row_obj in rows:
        cells = row_obj.get("row", [])
        row_data = []
        for cell in cells:
            text = cell.get("Text", "").strip()
            if text == "&nbsp;" or text == "":
                text = ""
            row_data.append(text)
        result.append(row_data)
    return result


def _parse_table_json(table_json_str):
    """JSON 문자열로 된 테이블 데이터를 파싱합니다."""
    if not table_json_str:
        return {"headers": [], "rows": [], "footer": []}

    data = json.loads(table_json_str)

    headers = []
    if data.get("headers"):
        for h in data["headers"]:
            headers.append([c.get("Text", "") for c in h.get("row", [])])

    rows = _extract_text(data.get("rows", []))
    footer = _extract_text(data.get("tfoot", []))

    return {"headers": headers, "rows": rows, "footer": footer}


def _parse_hitter(hitter_obj):
    """타자 데이터를 파싱합니다.

    table1: 선수 라인업 (타순, 포지션, 이름)
    table2: 이닝별 타석 결과
    table3: 타수/안타/타점/득점/타율
    """
    lineup = _parse_table_json(hitter_obj.get("table1", ""))
    at_bats = _parse_table_json(hitter_obj.get("table2", ""))
    stats = _parse_table_json(hitter_obj.get("table3", ""))

    batters = []
    for i, row in enumerate(lineup["rows"]):
        if len(row) >= 3:
            batter = {
                "order": row[0],
                "position": row[1],
                "name": row[2],
            }

            # 타석 결과 매칭
            if i < len(at_bats["rows"]):
                batter["innings"] = [x if x else None for x in at_bats["rows"][i]]

            # 타격 성적 매칭
            if i < len(stats["rows"]):
                s = stats["rows"][i]
                if len(s) >= 5:
                    batter["AB"] = s[0]  # 타수
                    batter["H"] = s[1]  # 안타
                    batter["RBI"] = s[2]  # 타점
                    batter["R"] = s[3]  # 득점
                    batter["AVG"] = s[4]  # 타율

            batters.append(batter)

    # 팀 합계
    total = {}
    if stats["footer"] and len(stats["footer"][0]) >= 5:
        f = stats["footer"][0]
        total = {"AB": f[0], "H": f[1], "RBI": f[2], "R": f[3], "AVG": f[4]}

    return {"batters": batters, "total": total}


def _parse_pitcher(pitcher_obj):
    """투수 데이터를 파싱합니다."""
    table = _parse_table_json(pitcher_obj.get("table", ""))

    header_keys = [
        "name",
        "entry",
        "result",
        "W",
        "L",
        "SV",
        "IP",
        "TBF",
        "NP",
        "AB",
        "H",
        "HR",
        "BB",
        "SO",
        "R",
        "ER",
        "ERA",
    ]

    pitchers = []
    for row in table["rows"]:
        pitcher = {}
        for j, val in enumerate(row):
            if j < len(header_keys):
                pitcher[header_keys[j]] = val if val else ""
        pitchers.append(pitcher)

    return pitchers


def _parse_etc(etc_json_str):
    """기타 경기 정보 (결승타, 홈런, 도루, 심판 등)를 파싱합니다."""
    table = _parse_table_json(etc_json_str)
    info = {}
    for row in table["rows"]:
        if len(row) >= 2 and row[0]:
            info[row[0]] = row[1].strip()
    return info


def _fetch_scoreboard(full_game_id, le_id=1, sr_id=0, season_id=None):
    """GetScoreBoardScroll API에서 이닝별 스코어보드를 가져옵니다."""
    if season_id is None:
        season_id = int(full_game_id[:4])

    data = {
        "leId": le_id,
        "srId": sr_id,
        "seasonId": season_id,
        "gameId": full_game_id,
    }
    resp = requests.post(SCOREBOARD_URL, data=data, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    # table2: 이닝별 점수 (headers=[1,2,...,N], rows=[away, home])
    table2 = _parse_table_json(result.get("table2", ""))
    innings = table2["headers"][0] if table2["headers"] else []
    away_scores = table2["rows"][0] if len(table2["rows"]) >= 1 else []
    home_scores = table2["rows"][1] if len(table2["rows"]) >= 2 else []

    # table3: R, H, E, BB 합계
    table3 = _parse_table_json(result.get("table3", ""))
    away_rheb = table3["rows"][0] if len(table3["rows"]) >= 1 else []
    home_rheb = table3["rows"][1] if len(table3["rows"]) >= 2 else []

    return {
        "innings": innings,
        "away": away_scores,
        "home": home_scores,
        "away_RHEB": away_rheb,
        "home_RHEB": home_rheb,
    }


def fetch_game(game_date, game_id, le_id=1, sr_id=0, season_id=None):
    """단일 경기의 상세 데이터를 가져옵니다.

    Args:
        game_date (str): "20260328" 형식
        game_id (str): "KTLG0" 형식
        le_id (int): 리그 ID (1=KBO)
        sr_id (int): 시리즈 ID (0=정규, 1=시범)
        season_id (int): 시즌 연도 (None이면 game_date에서 추출)

    Returns:
        dict: 경기 데이터
    """
    if season_id is None:
        season_id = int(game_date[:4])

    full_game_id = game_date + game_id

    data = {
        "leId": le_id,
        "srId": sr_id,
        "seasonId": season_id,
        "gameId": full_game_id,
    }

    resp = requests.post(BOXSCORE_URL, data=data, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    # 타자 파싱 (arrHitter: [away, home])
    hitters = result.get("arrHitter", [])
    away_batter = _parse_hitter(hitters[0]) if len(hitters) >= 1 else {}
    home_batter = _parse_hitter(hitters[1]) if len(hitters) >= 2 else {}

    # 투수 파싱 (arrPitcher: [away, home])
    pitchers = result.get("arrPitcher", [])
    away_pitcher = _parse_pitcher(pitchers[0]) if len(pitchers) >= 1 else []
    home_pitcher = _parse_pitcher(pitchers[1]) if len(pitchers) >= 2 else []

    # 기타 정보
    etc_info = _parse_etc(result.get("tableEtc", ""))

    # 스코어보드 (별도 API 호출)
    scoreboard = _fetch_scoreboard(full_game_id, le_id=le_id, sr_id=sr_id, season_id=season_id)

    return {
        "id": f"{game_date}_{game_id}",
        "contents": {
            "scoreboard": scoreboard,
            "ETC_info": etc_info,
            "away_batter": away_batter,
            "home_batter": home_batter,
            "away_pitcher": away_pitcher,
            "home_pitcher": home_pitcher,
        },
        "meta": {
            "maxInning": result.get("maxInning"),
            "realMaxInning": result.get("realMaxInning"),
        },
    }


def fetch_date(game_date, delay=1.0):
    """특정 날짜의 모든 경기 데이터를 수집합니다.

    Args:
        game_date (str): "20260328" 형식
        delay (float): 각 요청 사이 대기 시간 (초)

    Returns:
        list: 경기 데이터 목록
    """
    games = get_game_schedule.by_date(game_date)
    results = []

    for g in games:
        g_id = g.get("G_ID", "")
        if len(g_id) < 9:
            continue

        game_id = g_id[8:]
        sr_id = g.get("SR_ID", 0)
        season_id = g.get("SEASON_ID", int(game_date[:4]))

        # 취소 경기 건너뜀
        if g.get("CANCEL_SC_ID", "0") != "0":
            print(f"  건너뜀 (취소): {game_id}")
            continue

        print(f"  수집 중: {game_date} {game_id}")
        try:
            data = fetch_game(game_date, game_id, sr_id=sr_id, season_id=season_id)
            results.append(data)
        except Exception as e:
            print(f"  오류: {e}")

        if delay > 0:
            time.sleep(delay)

    return results


def fetch_month(year, month, delay=1.0, save=False):
    """한 달치 모든 경기 데이터를 수집합니다.

    이미 수집된 경기는 건너뛰고 새 경기만 수집합니다.

    Args:
        year (int): 연도 (예: 2026)
        month (int): 월 (1~12)
        delay (float): 각 요청 사이 대기 시간 (초)
        save (bool): True이면 data/game/{year}/{year}_{month}.json에 저장

    Returns:
        list: 전체 경기 데이터 목록 (기존 + 신규)
    """
    import calendar
    import os

    # 기존 데이터 로드
    dir_path = f"data/game/{year}"
    file_path = f"{dir_path}/{year}_{month:02d}.json"
    existing = []
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing_ids = {g["id"] for g in existing}

    new_count = 0
    _, last_day = calendar.monthrange(year, month)

    for day in range(1, last_day + 1):
        game_date = f"{year}{month:02d}{day:02d}"
        games = get_game_schedule.by_date(game_date)

        has_new = False
        for g in games:
            g_id = g.get("G_ID", "")
            if len(g_id) < 9:
                continue
            game_id = g_id[8:]
            full_id = f"{game_date}_{game_id}"

            if full_id in existing_ids:
                continue

            if g.get("CANCEL_SC_ID", "0") != "0":
                continue

            if not has_new:
                print(f"[{game_date}]")
                has_new = True

            sr_id = g.get("SR_ID", 0)
            season_id = g.get("SEASON_ID", int(game_date[:4]))

            print(f"  수집 중: {game_date} {game_id}")
            try:
                data = fetch_game(game_date, game_id, sr_id=sr_id, season_id=season_id)
                existing.append(data)
                existing_ids.add(full_id)
                new_count += 1
            except Exception as e:
                print(f"  오류: {e}")

            if delay > 0:
                time.sleep(delay)

    print(f"신규 {new_count}경기 수집 (총 {len(existing)}경기, {year}년 {month}월)")

    if save:
        os.makedirs(dir_path, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"저장 완료: {file_path}")

    return existing


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        gd = sys.argv[1]
        gid = sys.argv[2]
        sr = int(sys.argv[3]) if len(sys.argv) >= 4 else 0
        print(f"=== {gd} {gid} (srId={sr}) ===")
        data = fetch_game(gd, gid, sr_id=sr)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("사용법: python get_game_data.py 20260328 KTLG0 [srId]")
        print("  srId: 0=정규시즌, 1=시범경기")
