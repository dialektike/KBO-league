""" GitHub Actions을 이용해서 오늘 KBO 경기 schedule을 수집하는 모듈

Usage:
    # API 서버에 전송
    python for_github_actions.py $API_URL

    # 로컬 파일로 저장
    python for_github_actions.py --save
"""

import os
import sys
import json
from datetime import date

import requests

import get_game_schedule


if __name__ == "__main__":

    today_games = get_game_schedule.today(include_score=True)
    print(f"오늘 경기 수: {len(today_games)}")
    print(json.dumps(today_games, ensure_ascii=False, indent=2))

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == "--save":
            # 로컬 파일로 저장
            os.makedirs("data/schedule", exist_ok=True)
            today_str = date.today().strftime("%Y_%m_%d")
            filename = f"data/schedule/{today_str}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(today_games, f, ensure_ascii=False, indent=2)
            print(f"저장 완료: {filename}")

        else:
            # API 서버에 POST
            url = arg
            r = requests.post(url, json=today_games)
            print(f"POST 응답: {r.status_code}")
