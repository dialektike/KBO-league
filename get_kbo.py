"""KBO 경기 데이터 수집 스크립트

스케줄 CSV 저장 → 경기 데이터 수집 → 기존 포맷 변환을 한번에 실행합니다.

Usage:
    # 특정 월 수집
    python get_kbo.py 2026 4

    # 여러 달 수집
    python get_kbo.py 2026 4 10

    # 연도 전체 수집 (3~10월)
    python get_kbo.py 2026
"""

import sys

import get_game_schedule
import get_game_data
import convert_game_data


def collect(year, month, delay=0.5, base_dir="."):
    """한 달치 데이터를 수집하고 변환합니다.

    1) 스케줄 CSV 저장
    2) 경기 데이터 수집 + JSON 저장
    3) 기존 포맷으로 변환

    저장 구조: {base_dir}/data/game/{year}/, {base_dir}/data/schedule/{year}/

    Args:
        year (int): 연도
        month (int): 월
        delay (float): 각 요청 사이 대기 시간 (초)
        base_dir (str): 데이터 루트 디렉토리 (기본값: ".")
    """
    print(f"=== {year}년 {month}월 ===")

    print("[1/3] 스케줄 CSV 저장")
    get_game_schedule.save_month_csv(year, month, base_dir=base_dir)

    print("[2/3] 경기 데이터 수집")
    get_game_data.fetch_month(year, month, delay=delay, save=True, base_dir=base_dir)

    game_file = get_game_data._game_file_path(year, month, base_dir)
    print("[3/3] 기존 포맷으로 변환")
    convert_game_data.convert_file(game_file)

    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="KBO 경기 데이터 수집")
    parser.add_argument("year", type=int, help="연도 (예: 2026)")
    parser.add_argument("start_month", type=int, nargs="?", default=None,
                        help="시작 월 (생략 시 3~10월)")
    parser.add_argument("end_month", type=int, nargs="?", default=None,
                        help="종료 월 (생략 시 시작 월과 동일)")
    parser.add_argument("-d", "--base-dir", default=".",
                        help="데이터 루트 디렉토리. 이 아래에 data/game/, data/schedule/ 생성 (기본값: .)")

    args = parser.parse_args()

    if args.start_month is None:
        start, end = 3, 10
    elif args.end_month is None:
        start = end = args.start_month
    else:
        start = args.start_month
        end = args.end_month

    for month in range(start, end + 1):
        collect(args.year, month, base_dir=args.base_dir)

    print("수집 완료")
