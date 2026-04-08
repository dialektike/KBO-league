"""신규 수집 데이터를 기존(2001~2021) 포맷으로 변환하는 모듈

신규 포맷(get_game_data.py 수집)을 기존 포맷에 맞춰 변환합니다.
변환 후 get.game_data()로 통합 조회가 가능해집니다.

Usage:
    # 단일 파일 변환
    python convert_game_data.py data/game/2025/2025_04.json

    # 연도 전체 변환
    python convert_game_data.py data/game/2025/

    # 모듈로 사용
    import convert_game_data
    convert_game_data.convert_file("data/game/2025/2025_04.json")
"""

import json
import os
import sys

TEAM_NAMES = {
    "HT": "KIA",
    "OB": "두산",
    "LT": "롯데",
    "NC": "NC",
    "SK": "SSG",
    "LG": "LG",
    "WO": "키움",
    "HH": "한화",
    "SS": "삼성",
    "KT": "KT",
}


def _team_name(team_id):
    """팀 ID를 팀 이름으로 변환합니다."""
    return TEAM_NAMES.get(team_id, team_id)


def _parse_game_id(game_id):
    """게임 ID에서 원정팀/홈팀 ID를 추출합니다.

    예: '20250402_WOOB0' → ('WO', 'OB')
    """
    code = game_id.split("_")[1] if "_" in game_id else game_id[8:]
    away_id = code[:2]
    home_id = code[2:4]
    return away_id, home_id


def _to_num(val):
    """문자열을 숫자로 변환합니다. 실패하면 원래 값을 반환합니다."""
    if val is None or val == "" or val == "-":
        return val
    try:
        if "." in str(val):
            return float(val)
        return int(val)
    except (ValueError, TypeError):
        return val


def _convert_scoreboard(scoreboard, away_id, home_id, away_rheb=None, home_rheb=None):
    """스코어보드를 기존 포맷으로 변환합니다."""
    innings = scoreboard.get("innings", [])
    away_scores = scoreboard.get("away", [])
    home_scores = scoreboard.get("home", [])
    away_rheb = scoreboard.get("away_RHEB", away_rheb or [])
    home_rheb = scoreboard.get("home_RHEB", home_rheb or [])

    away_r = _to_num(away_rheb[0]) if len(away_rheb) > 0 else 0
    home_r = _to_num(home_rheb[0]) if len(home_rheb) > 0 else 0

    if away_r > home_r:
        away_wl, home_wl = "승", "패"
    elif away_r < home_r:
        away_wl, home_wl = "패", "승"
    else:
        away_wl, home_wl = "무", "무"

    def build_team_row(team_id, wl, scores, rheb):
        row = {"팀": _team_name(team_id), "승패": wl}
        for i in range(12):
            inning_num = str(i + 1)
            if i < len(scores):
                row[inning_num] = _to_num(scores[i])
            else:
                row[inning_num] = "-"
        row["R"] = _to_num(rheb[0]) if len(rheb) > 0 else 0
        row["H"] = _to_num(rheb[1]) if len(rheb) > 1 else 0
        row["E"] = _to_num(rheb[2]) if len(rheb) > 2 else 0
        row["B"] = _to_num(rheb[3]) if len(rheb) > 3 else 0
        return row

    return [
        build_team_row(away_id, away_wl, away_scores, away_rheb),
        build_team_row(home_id, home_wl, home_scores, home_rheb),
    ]


def _convert_batters(batter_data, team_id):
    """타자 데이터를 기존 포맷으로 변환합니다."""
    if not batter_data or not batter_data.get("batters"):
        return []

    result = []
    for b in batter_data["batters"]:
        row = {
            "포지션": b.get("position", ""),
            "선수명": b.get("name", ""),
        }
        innings = b.get("innings", [])
        for i in range(9):
            inning_num = str(i + 1)
            if i < len(innings):
                val = innings[i]
                row[inning_num] = val if val is not None else 0
            else:
                row[inning_num] = 0

        row["타수"] = _to_num(b.get("AB", 0))
        row["안타"] = _to_num(b.get("H", 0))
        row["타점"] = _to_num(b.get("RBI", 0))
        row["득점"] = _to_num(b.get("R", 0))
        row["타율"] = _to_num(b.get("AVG", 0))
        row["팀"] = _team_name(team_id)
        result.append(row)

    return result


def _convert_pitchers(pitcher_list, team_id):
    """투수 데이터를 기존 포맷으로 변환합니다."""
    result = []
    for p in pitcher_list:
        row = {
            "선수명": p.get("name", ""),
            "등판": p.get("entry", ""),
            "결과": p.get("result", ""),
            "승": p.get("W", "0"),
            "패": p.get("L", "0"),
            "세": p.get("SV", "0"),
            "이닝": p.get("IP", "0"),
            "타자": _to_num(p.get("TBF", 0)),
            "투구수": _to_num(p.get("NP", 0)),
            "타수": _to_num(p.get("AB", 0)),
            "피안타": _to_num(p.get("H", 0)),
            "홈런": _to_num(p.get("HR", 0)),
            "4사구": _to_num(p.get("BB", 0)),
            "삼진": _to_num(p.get("SO", 0)),
            "실점": _to_num(p.get("R", 0)),
            "자책": _to_num(p.get("ER", 0)),
            "평균자책점": _to_num(p.get("ERA", 0)),
            "팀": _team_name(team_id),
        }
        result.append(row)

    return result


def _convert_etc(etc_info):
    """ETC_info를 기존 포맷으로 변환합니다."""
    result = {}
    for key, val in etc_info.items():
        if key == "심판" and isinstance(val, str):
            result[key] = val.split()
        else:
            result[key] = val
    return result


def convert_game(game):
    """단일 경기 데이터를 기존 포맷으로 변환합니다."""
    game_id = game["id"]
    contents = game["contents"]
    away_id, home_id = _parse_game_id(game_id)

    return {
        "id": game_id,
        "contents": {
            "scoreboard": _convert_scoreboard(
                contents.get("scoreboard", {}), away_id, home_id
            ),
            "ETC_info": _convert_etc(contents.get("ETC_info", {})),
            "away_batter": _convert_batters(
                contents.get("away_batter", {}), away_id
            ),
            "home_batter": _convert_batters(
                contents.get("home_batter", {}), home_id
            ),
            "away_pitcher": _convert_pitchers(
                contents.get("away_pitcher", []), away_id
            ),
            "home_pitcher": _convert_pitchers(
                contents.get("home_pitcher", []), home_id
            ),
        },
    }


def convert_file(file_path):
    """JSON 파일을 기존 포맷으로 변환하여 덮어씁니다.

    Returns:
        int: 변환된 경기 수
    """
    with open(file_path, "r", encoding="utf-8") as f:
        games = json.load(f)

    # 이미 기존 포맷인지 확인 (기존 포맷: scoreboard가 list, 신규 포맷: meta 키 존재)
    if games:
        first = games[0]
        scoreboard = first.get("contents", {}).get("scoreboard")
        has_meta = "meta" in first
        if isinstance(scoreboard, list) and not has_meta:
            print(f"  건너뜀 (이미 기존 포맷): {file_path}")
            return 0

    converted = [convert_game(g) for g in games]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(converted, f, ensure_ascii=False, indent=2)

    print(f"  변환 완료: {file_path} ({len(converted)}경기)")
    return len(converted)


def convert_dir(dir_path):
    """디렉토리 내 모든 JSON 파일을 변환합니다.

    Returns:
        int: 변환된 총 경기 수
    """
    total = 0
    for f in sorted(os.listdir(dir_path)):
        if f.endswith(".json"):
            total += convert_file(os.path.join(dir_path, f))
    return total


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법:")
        print("  python convert_game_data.py data/game/2025/2025_04.json")
        print("  python convert_game_data.py data/game/2025/")
        sys.exit(1)

    path = sys.argv[1]

    if os.path.isdir(path):
        total = convert_dir(path)
    elif os.path.isfile(path):
        total = convert_file(path)
    else:
        print(f"파일/디렉토리를 찾을 수 없음: {path}")
        sys.exit(1)

    print(f"총 {total}경기 변환 완료")
