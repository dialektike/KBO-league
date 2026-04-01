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


def collect(year, month, delay=0.5):
    """한 달치 데이터를 수집하고 변환합니다.

    1) 스케줄 CSV 저장
    2) 경기 데이터 수집 + JSON 저장
    3) 기존 포맷으로 변환
    """
    print(f"=== {year}년 {month}월 ===")

    print("[1/3] 스케줄 CSV 저장")
    get_game_schedule.save_month_csv(year, month)

    print("[2/3] 경기 데이터 수집")
    get_game_data.fetch_month(year, month, delay=delay, save=True)

    print("[3/3] 기존 포맷으로 변환")
    convert_game_data.convert_file(f"data/game/{year}/{year}_{month:02d}.json")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법:")
        print("  python get_kbo.py 2026 4        # 특정 월")
        print("  python get_kbo.py 2026 4 10     # 4~10월")
        print("  python get_kbo.py 2026           # 전체 (3~10월)")
        sys.exit(1)

    year = int(sys.argv[1])

    if len(sys.argv) == 2:
        start, end = 3, 10
    elif len(sys.argv) == 3:
        start = end = int(sys.argv[2])
    else:
        start = int(sys.argv[2])
        end = int(sys.argv[3])

    for month in range(start, end + 1):
        collect(year, month)

    print("수집 완료")
