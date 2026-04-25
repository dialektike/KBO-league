"""KBO 경기 데이터 수집 스크립트

스케줄 CSV 저장 → 경기 데이터 수집을 한번에 실행합니다.

Usage:
    # 특정 월 수집
    python get_kbo.py 2026 4

    # 여러 달 수집
    python get_kbo.py 2026 4 10

    # 연도 전체 수집 (2~11월: 시범~포스트시즌)
    python get_kbo.py 2026
"""

import get_game_schedule
import get_game_data
import settings


def collect(year, month, delay=None, base_dir=None):
    """한 달치 데이터를 수집합니다.

    1) 스케줄 CSV 저장
    2) 경기 데이터 수집 + JSON 저장 (신규 포맷 그대로)

    저장 구조: {base_dir}/data/game/{year}/, {base_dir}/data/schedule/{year}/

    Args:
        year (int): 연도
        month (int): 월
        delay (float): 각 요청 사이 대기 시간 (초, None이면 config.ini 설정값 사용)
        base_dir (str): 데이터 루트 디렉토리 (None이면 config.ini 설정값 사용)
    """
    if delay is None:
        delay = settings.DELAY
    if base_dir is None:
        base_dir = settings.BASE_DIR
    print(f"=== {year}년 {month}월 ===")

    print("[1/2] 스케줄 CSV 저장")
    get_game_schedule.save_month_csv(year, month, base_dir=base_dir)

    print("[2/2] 경기 데이터 수집")
    get_game_data.fetch_month(year, month, delay=delay, save=True, base_dir=base_dir)

    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="KBO 경기 데이터 수집")
    parser.add_argument("year", type=int, help="연도 (예: 2026)")
    parser.add_argument("start_month", type=int, nargs="?", default=None,
                        help="시작 월 (생략 시 2~11월: 시범~포스트시즌)")
    parser.add_argument("end_month", type=int, nargs="?", default=None,
                        help="종료 월 (생략 시 시작 월과 동일)")
    parser.add_argument("-d", "--base-dir", default=settings.BASE_DIR,
                        help=f"데이터 루트 디렉토리. 이 아래에 data/game/, data/schedule/ 생성 "
                             f"(기본값: {settings.BASE_DIR}, config.ini에서 변경 가능)")

    args = parser.parse_args()

    if args.start_month is None:
        start, end = 2, 11
    elif args.end_month is None:
        start = end = args.start_month
    else:
        start = args.start_month
        end = args.end_month

    for month in range(start, end + 1):
        collect(args.year, month, base_dir=args.base_dir)

    print("수집 완료")
