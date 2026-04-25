"""KBO 경기 JSON 데이터를 DuckDB로 적재하는 ETL.

8개 테이블로 정규화하여 분석에 적합한 형태로 저장합니다.

Usage:
    # 전체 재구축
    python build_duckdb.py --rebuild

    # 특정 연도만 (멱등 적재)
    python build_duckdb.py --year 2026

    # 여러 연도
    python build_duckdb.py --year 2024 --year 2025 --year 2026

    # 검증 쿼리 실행
    python build_duckdb.py --validate

    # DB 파일 경로 지정 (기본값: config.ini의 [duckdb] path)
    python build_duckdb.py --rebuild --db /path/to/kbo.duckdb
"""

import argparse
import csv
import glob
import json
import os
import re
from collections import defaultdict
from datetime import date

import duckdb
import polars as pl

import settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS games (
    game_id        VARCHAR PRIMARY KEY,
    g_dt           DATE,
    g_tm           VARCHAR,
    season         SMALLINT,
    sr_id          TINYINT,
    sr_nm          VARCHAR,
    stadium        VARCHAR,
    away_team      VARCHAR,
    home_team      VARCHAR,
    away_team_nm   VARCHAR,
    home_team_nm   VARCHAR,
    away_runs      SMALLINT,
    home_runs      SMALLINT,
    max_inning     SMALLINT,
    real_max_inning SMALLINT,
    winner_side    VARCHAR,
    cancel_sc_nm   VARCHAR
);

CREATE TABLE IF NOT EXISTS team_box (
    game_id    VARCHAR,
    team_side  VARCHAR,
    team       VARCHAR,
    runs       SMALLINT,
    hits       SMALLINT,
    errors     SMALLINT,
    bb_total   SMALLINT,
    result     VARCHAR
);

CREATE TABLE IF NOT EXISTS linescore (
    game_id    VARCHAR,
    team_side  VARCHAR,
    team       VARCHAR,
    inning     SMALLINT,
    runs       SMALLINT
);

CREATE TABLE IF NOT EXISTS batting_lines (
    game_id        VARCHAR,
    team_side      VARCHAR,
    team           VARCHAR,
    batting_order  SMALLINT,
    sub_order      SMALLINT,
    position       VARCHAR,
    player_name    VARCHAR,
    ab             SMALLINT,
    h              SMALLINT,
    rbi            SMALLINT,
    r              SMALLINT,
    avg            DOUBLE
);

CREATE TABLE IF NOT EXISTS batting_pa (
    game_id        VARCHAR,
    team_side      VARCHAR,
    batting_order  SMALLINT,
    sub_order      SMALLINT,
    player_name    VARCHAR,
    inning         SMALLINT,
    result         VARCHAR
);

CREATE TABLE IF NOT EXISTS pitching_lines (
    game_id           VARCHAR,
    team_side         VARCHAR,
    team              VARCHAR,
    appearance_order  SMALLINT,
    player_name       VARCHAR,
    role              VARCHAR,
    decision          VARCHAR,
    w                 SMALLINT,
    l                 SMALLINT,
    sv                SMALLINT,
    ip_outs           SMALLINT,
    tbf               SMALLINT,
    pitches           SMALLINT,
    ab                SMALLINT,
    h                 SMALLINT,
    hr                SMALLINT,
    bb_hbp            SMALLINT,
    so                SMALLINT,
    r                 SMALLINT,
    er                SMALLINT,
    era               DOUBLE
);

CREATE TABLE IF NOT EXISTS game_events (
    game_id     VARCHAR,
    event_type  VARCHAR,
    raw_text    VARCHAR
);

CREATE TABLE IF NOT EXISTS umpires (
    game_id   VARCHAR,
    position  VARCHAR,
    name      VARCHAR
);
"""

UMPIRE_POSITIONS = ["주심", "1루심", "2루심", "3루심", "좌선심", "우선심"]


def _to_int(v):
    if v is None or v == "" or v == "-":
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _to_float(v):
    if v is None or v == "" or v == "-":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


_IP_RE = re.compile(r"^\s*(\d+)(?:\s*(\d)\s*/\s*3)?\s*$|^\s*(\d+)\.(\d)\s*$")


def _ip_to_outs(ip):
    """이닝 표기를 outs(정수)로 변환.

    "5"     → 15
    "5.1"   → 16
    "5.2"   → 17
    "5 1/3" → 16
    """
    if ip is None or ip == "" or ip == "-":
        return None
    s = str(ip).strip()
    # "5.1" / "5.2" 형식
    if "." in s:
        try:
            whole, frac = s.split(".", 1)
            return int(whole) * 3 + int(frac)
        except ValueError:
            return None
    # "5 1/3" 형식
    if "/" in s:
        m = re.match(r"^\s*(\d+)\s+(\d)\s*/\s*3\s*$", s)
        if m:
            return int(m.group(1)) * 3 + int(m.group(2))
        m = re.match(r"^\s*(\d)\s*/\s*3\s*$", s)
        if m:
            return int(m.group(1))
        return None
    # "5" 형식
    try:
        return int(s) * 3
    except ValueError:
        return None


def _parse_team_ids(game_id):
    """'20010405_LGSK0' → ('LG', 'SK')."""
    code = game_id.split("_", 1)[1]
    return code[:2], code[2:4]


def _winner_side(away_r, home_r):
    if away_r is None or home_r is None:
        return None
    if away_r > home_r:
        return "away"
    if away_r < home_r:
        return "home"
    return "draw"


def _result_label(side, winner_side):
    if winner_side is None:
        return None
    if winner_side == "draw":
        return "무"
    return "승" if side == winner_side else "패"


def _safe_get(arr, i, default=None):
    return arr[i] if i < len(arr) else default


# ---------- Schedule loader ----------


def load_schedule_meta(year, base_dir=None):
    """연도별 스케줄 CSV에서 game_id → 메타정보 dict 생성.

    Returns:
        dict: {full_game_id (with underscore): {sr_id, sr_nm, stadium, g_tm, away_id, home_id, away_nm, home_nm, cancel_sc_nm}}
    """
    if base_dir is None:
        base_dir = settings.BASE_DIR
    meta = {}
    for csv_path in sorted(glob.glob(os.path.join(base_dir, "data/schedule", str(year), f"{year}_*.csv"))):
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                gid_raw = row.get("G_ID", "")
                if not gid_raw or len(gid_raw) < 9:
                    continue
                # CSV는 underscore 없음: 20010405LGSK0 → 20010405_LGSK0
                full_id = f"{gid_raw[:8]}_{gid_raw[8:]}"
                meta[full_id] = {
                    "sr_id": _to_int(row.get("SR_ID")),
                    "sr_nm": row.get("SR_NM") or None,
                    "stadium": row.get("S_NM") or None,
                    "g_tm": row.get("G_TM") or None,
                    "away_id": row.get("AWAY_ID") or None,
                    "home_id": row.get("HOME_ID") or None,
                    "away_nm": row.get("AWAY_NM") or None,
                    "home_nm": row.get("HOME_NM") or None,
                    "cancel_sc_nm": row.get("CANCEL_SC_NM") or None,
                }
    return meta


# ---------- Per-game parsing ----------


def parse_game(game, sched_meta=None):
    """단일 경기 dict → 8개 테이블용 row 리스트 묶음."""
    rows = {k: [] for k in (
        "games", "team_box", "linescore", "batting_lines",
        "batting_pa", "pitching_lines", "game_events", "umpires",
    )}

    game_id = game.get("id")
    if not game_id:
        return rows

    contents = game.get("contents", {})
    meta = game.get("meta", {}) or {}

    away_id, home_id = _parse_team_ids(game_id)
    g_dt_str = game_id[:8]
    season = int(g_dt_str[:4])
    g_dt = date(int(g_dt_str[:4]), int(g_dt_str[4:6]), int(g_dt_str[6:8]))

    sb = contents.get("scoreboard") or {}
    away_rheb = sb.get("away_RHEB") or []
    home_rheb = sb.get("home_RHEB") or []
    away_r = _to_int(_safe_get(away_rheb, 0))
    home_r = _to_int(_safe_get(home_rheb, 0))
    winner = _winner_side(away_r, home_r)

    s = sched_meta.get(game_id, {}) if sched_meta else {}

    # ---- games ----
    rows["games"].append({
        "game_id": game_id,
        "g_dt": g_dt,
        "g_tm": s.get("g_tm"),
        "season": season,
        "sr_id": s.get("sr_id"),
        "sr_nm": s.get("sr_nm"),
        "stadium": s.get("stadium"),
        "away_team": away_id,
        "home_team": home_id,
        "away_team_nm": s.get("away_nm"),
        "home_team_nm": s.get("home_nm"),
        "away_runs": away_r,
        "home_runs": home_r,
        "max_inning": _to_int(meta.get("maxInning")),
        "real_max_inning": _to_int(meta.get("realMaxInning")),
        "winner_side": winner,
        "cancel_sc_nm": s.get("cancel_sc_nm"),
    })

    # ---- team_box (스코어보드 데이터 있을 때만) ----
    if away_rheb and home_rheb:
        for side, team, rheb in (("away", away_id, away_rheb), ("home", home_id, home_rheb)):
            rows["team_box"].append({
                "game_id": game_id,
                "team_side": side,
                "team": team,
                "runs": _to_int(_safe_get(rheb, 0)),
                "hits": _to_int(_safe_get(rheb, 1)),
                "errors": _to_int(_safe_get(rheb, 2)),
                "bb_total": _to_int(_safe_get(rheb, 3)),
                "result": _result_label(side, winner),
            })

    # ---- linescore ----
    innings = sb.get("innings") or []
    away_scores = sb.get("away") or []
    home_scores = sb.get("home") or []
    for side, team, scores in (("away", away_id, away_scores), ("home", home_id, home_scores)):
        for idx, raw in enumerate(scores):
            if raw in (None, "", "-"):
                continue
            inn = _to_int(_safe_get(innings, idx, idx + 1)) or (idx + 1)
            r = _to_int(raw)
            if r is None:
                continue
            rows["linescore"].append({
                "game_id": game_id,
                "team_side": side,
                "team": team,
                "inning": inn,
                "runs": r,
            })

    # ---- batting_lines + batting_pa ----
    for side, team, key in (("away", away_id, "away_batter"), ("home", home_id, "home_batter")):
        bdata = contents.get(key) or {}
        if not isinstance(bdata, dict):
            continue
        batters = bdata.get("batters") or []
        sub_counter = defaultdict(int)
        for b in batters:
            order = _to_int(b.get("order"))
            if order is None:
                continue
            sub_counter[order] += 1
            sub_order = sub_counter[order]
            name = b.get("name") or ""
            position = b.get("position") or ""
            rows["batting_lines"].append({
                "game_id": game_id,
                "team_side": side,
                "team": team,
                "batting_order": order,
                "sub_order": sub_order,
                "position": position,
                "player_name": name,
                "ab": _to_int(b.get("AB")),
                "h": _to_int(b.get("H")),
                "rbi": _to_int(b.get("RBI")),
                "r": _to_int(b.get("R")),
                "avg": _to_float(b.get("AVG")),
            })
            for inn_idx, raw in enumerate(b.get("innings") or []):
                if not raw:  # None / 0 / "" → 타석 없음
                    continue
                rows["batting_pa"].append({
                    "game_id": game_id,
                    "team_side": side,
                    "batting_order": order,
                    "sub_order": sub_order,
                    "player_name": name,
                    "inning": inn_idx + 1,
                    "result": str(raw),
                })

    # ---- pitching_lines ----
    for side, team, key in (("away", away_id, "away_pitcher"), ("home", home_id, "home_pitcher")):
        pitchers = contents.get(key) or []
        if not isinstance(pitchers, list):
            continue
        for idx, p in enumerate(pitchers, start=1):
            rows["pitching_lines"].append({
                "game_id": game_id,
                "team_side": side,
                "team": team,
                "appearance_order": idx,
                "player_name": p.get("name") or "",
                "role": p.get("entry") or None,
                "decision": p.get("result") or None,
                "w": _to_int(p.get("W")),
                "l": _to_int(p.get("L")),
                "sv": _to_int(p.get("SV")),
                "ip_outs": _ip_to_outs(p.get("IP")),
                "tbf": _to_int(p.get("TBF")),
                "pitches": _to_int(p.get("NP")),
                "ab": _to_int(p.get("AB")),
                "h": _to_int(p.get("H")),
                "hr": _to_int(p.get("HR")),
                "bb_hbp": _to_int(p.get("BB")),
                "so": _to_int(p.get("SO")),
                "r": _to_int(p.get("R")),
                "er": _to_int(p.get("ER")),
                "era": _to_float(p.get("ERA")),
            })

    # ---- game_events + umpires ----
    etc = contents.get("ETC_info") or {}
    if isinstance(etc, dict):
        for ev_type, raw_text in etc.items():
            if ev_type == "심판":
                # 신규 포맷: 공백으로 구분된 문자열, 구포맷 호환: list
                names = raw_text.split() if isinstance(raw_text, str) else (raw_text or [])
                for i, nm in enumerate(names):
                    pos = UMPIRE_POSITIONS[i] if i < len(UMPIRE_POSITIONS) else f"심판{i+1}"
                    rows["umpires"].append({
                        "game_id": game_id,
                        "position": pos,
                        "name": nm,
                    })
                continue
            if raw_text in (None, "", "없음"):
                continue
            rows["game_events"].append({
                "game_id": game_id,
                "event_type": ev_type,
                "raw_text": str(raw_text),
            })

    return rows


# ---------- DuckDB load ----------


TABLE_NAMES = [
    "games", "team_box", "linescore", "batting_lines",
    "batting_pa", "pitching_lines", "game_events", "umpires",
]


# 스키마와 일치시키기 위한 명시적 polars 타입 매핑.
# DuckDB는 PyArrow로 polars 테이블을 받으므로 SMALLINT 컬럼이 빈 결과면 polars에서 INT64로 추론될 수 있음.
COLUMN_DTYPES = {
    "games": {
        "game_id": pl.Utf8, "g_dt": pl.Date, "g_tm": pl.Utf8,
        "season": pl.Int16, "sr_id": pl.Int8, "sr_nm": pl.Utf8,
        "stadium": pl.Utf8, "away_team": pl.Utf8, "home_team": pl.Utf8,
        "away_team_nm": pl.Utf8, "home_team_nm": pl.Utf8,
        "away_runs": pl.Int16, "home_runs": pl.Int16,
        "max_inning": pl.Int16, "real_max_inning": pl.Int16,
        "winner_side": pl.Utf8, "cancel_sc_nm": pl.Utf8,
    },
    "team_box": {
        "game_id": pl.Utf8, "team_side": pl.Utf8, "team": pl.Utf8,
        "runs": pl.Int16, "hits": pl.Int16, "errors": pl.Int16,
        "bb_total": pl.Int16, "result": pl.Utf8,
    },
    "linescore": {
        "game_id": pl.Utf8, "team_side": pl.Utf8, "team": pl.Utf8,
        "inning": pl.Int16, "runs": pl.Int16,
    },
    "batting_lines": {
        "game_id": pl.Utf8, "team_side": pl.Utf8, "team": pl.Utf8,
        "batting_order": pl.Int16, "sub_order": pl.Int16,
        "position": pl.Utf8, "player_name": pl.Utf8,
        "ab": pl.Int16, "h": pl.Int16, "rbi": pl.Int16, "r": pl.Int16,
        "avg": pl.Float64,
    },
    "batting_pa": {
        "game_id": pl.Utf8, "team_side": pl.Utf8,
        "batting_order": pl.Int16, "sub_order": pl.Int16,
        "player_name": pl.Utf8, "inning": pl.Int16, "result": pl.Utf8,
    },
    "pitching_lines": {
        "game_id": pl.Utf8, "team_side": pl.Utf8, "team": pl.Utf8,
        "appearance_order": pl.Int16, "player_name": pl.Utf8,
        "role": pl.Utf8, "decision": pl.Utf8,
        "w": pl.Int16, "l": pl.Int16, "sv": pl.Int16,
        "ip_outs": pl.Int16, "tbf": pl.Int16, "pitches": pl.Int16,
        "ab": pl.Int16, "h": pl.Int16, "hr": pl.Int16,
        "bb_hbp": pl.Int16, "so": pl.Int16,
        "r": pl.Int16, "er": pl.Int16, "era": pl.Float64,
    },
    "game_events": {
        "game_id": pl.Utf8, "event_type": pl.Utf8, "raw_text": pl.Utf8,
    },
    "umpires": {
        "game_id": pl.Utf8, "position": pl.Utf8, "name": pl.Utf8,
    },
}


def _to_df(rows, table):
    schema = COLUMN_DTYPES[table]
    if not rows:
        return pl.DataFrame(schema=schema)
    return pl.DataFrame(rows, schema=schema)


def init_schema(con, drop_first=False):
    if drop_first:
        for t in TABLE_NAMES:
            con.execute(f"DROP TABLE IF EXISTS {t}")
    con.execute(SCHEMA_SQL)


def load_year(con, year, base_dir=None):
    """한 연도의 모든 JSON을 읽어 8개 테이블에 멱등 적재."""
    if base_dir is None:
        base_dir = settings.BASE_DIR

    sched_meta = load_schedule_meta(year, base_dir=base_dir)
    files = sorted(glob.glob(os.path.join(base_dir, "data/game", str(year), f"{year}_*.json")))
    if not files:
        print(f"  {year}: JSON 파일 없음")
        return 0

    accum = {t: [] for t in TABLE_NAMES}
    n_games = 0
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            games = json.load(f)
        for g in games:
            parsed = parse_game(g, sched_meta=sched_meta)
            for t in TABLE_NAMES:
                accum[t].extend(parsed[t])
            n_games += 1

    if n_games == 0:
        print(f"  {year}: 경기 0건")
        return 0

    # 멱등 적재: 해당 연도 game_id를 모두 삭제 후 INSERT
    game_ids = [r["game_id"] for r in accum["games"]]
    if game_ids:
        ids_df = pl.DataFrame({"game_id": game_ids}, schema={"game_id": pl.Utf8})  # noqa: F841
        for t in TABLE_NAMES:
            con.execute(f"DELETE FROM {t} WHERE game_id IN (SELECT game_id FROM ids_df)")

    for t in TABLE_NAMES:
        df = _to_df(accum[t], t)  # noqa: F841
        con.execute(f"INSERT INTO {t} SELECT * FROM df")

    print(f"  {year}: {n_games}경기 적재")
    return n_games


def build(years, db_path, base_dir=None, rebuild=False):
    con = duckdb.connect(db_path)
    init_schema(con, drop_first=rebuild)
    total = 0
    for y in years:
        total += load_year(con, y, base_dir=base_dir)
    con.close()
    print(f"\n적재 완료: 총 {total}경기 → {db_path}")


# ---------- Validation ----------


VALIDATION_QUERIES = [
    ("게임 수", "SELECT COUNT(*) FROM games"),
    ("연도별 경기 수", "SELECT season, COUNT(*) FROM games GROUP BY season ORDER BY season"),
    ("team_box 행 수 (게임 수 × 2 기대)", "SELECT COUNT(*) FROM team_box"),
    ("선수-경기 타격 라인", "SELECT COUNT(*) FROM batting_lines"),
    ("타석 결과 행", "SELECT COUNT(*) FROM batting_pa"),
    ("투수 등판 행", "SELECT COUNT(*) FROM pitching_lines"),
    ("이벤트 행", "SELECT COUNT(*) FROM game_events"),
    ("심판 행", "SELECT COUNT(*) FROM umpires"),
    ("scoreboard R 합 vs linescore inning runs 합 (불일치 game 수)", """
        SELECT COUNT(*) FROM (
            SELECT tb.game_id
            FROM team_box tb
            LEFT JOIN (
                SELECT game_id, team_side, SUM(runs) AS inn_sum
                FROM linescore GROUP BY game_id, team_side
            ) ls ON tb.game_id = ls.game_id AND tb.team_side = ls.team_side
            WHERE tb.runs IS NOT NULL AND COALESCE(ls.inn_sum, 0) <> tb.runs
        )
    """),
    ("샘플: 2010년 KIA 홈 승률", """
        SELECT
            ROUND(AVG(CASE WHEN result='승' THEN 1 ELSE 0 END), 3) AS win_pct,
            COUNT(*) AS games
        FROM team_box tb JOIN games g USING(game_id)
        WHERE g.season = 2010 AND tb.team_side = 'home' AND tb.team = 'HT'
          AND result IN ('승','패')
    """),
]


def validate(db_path):
    con = duckdb.connect(db_path, read_only=True)
    for label, q in VALIDATION_QUERIES:
        try:
            result = con.execute(q).fetchall()
            if len(result) == 1 and len(result[0]) == 1:
                print(f"{label}: {result[0][0]}")
            else:
                print(f"{label}:")
                for row in result:
                    print(f"  {row}")
        except Exception as e:
            print(f"{label}: 오류 - {e}")
    con.close()


# ---------- CLI ----------


def main():
    ap = argparse.ArgumentParser(description="KBO 경기 데이터를 DuckDB로 적재")
    ap.add_argument("--year", type=int, action="append",
                    help="적재할 연도 (반복 가능). 미지정 시 모든 연도.")
    ap.add_argument("--rebuild", action="store_true",
                    help="모든 테이블을 DROP 후 재생성")
    ap.add_argument("--validate", action="store_true",
                    help="적재 후 검증 쿼리 실행")
    ap.add_argument("--db", default=settings.DUCKDB_PATH,
                    help=f"DuckDB 파일 경로 (기본값: {settings.DUCKDB_PATH})")
    ap.add_argument("-d", "--base-dir", default=settings.BASE_DIR,
                    help=f"데이터 루트 디렉토리 (기본값: {settings.BASE_DIR})")
    args = ap.parse_args()

    if args.year:
        years = sorted(set(args.year))
    else:
        years = sorted(int(os.path.basename(p)) for p in glob.glob(
            os.path.join(args.base_dir, "data/game", "*"))
            if os.path.basename(p).isdigit())

    if not years and not args.validate:
        ap.error("적재할 연도가 없습니다. data/game/{year}/ 디렉토리를 확인하세요.")

    if years:
        build(years, args.db, base_dir=args.base_dir, rebuild=args.rebuild)

    if args.validate:
        print("\n=== 검증 ===")
        validate(args.db)


if __name__ == "__main__":
    main()
