""" github actions을 이용해서 오늘 KBO 경기 schedule를 가져와 API 서버에 저장하는 모듈


Example:

"""

import sys
import json

import requests

import get_game_schedule

if __name__ == "__main__":
    
    today_schedule = get_game_schedule.today()
    # 오늘 schedule이 잘 들어왔는지 확인
    print(today_schedule)

    url = str(sys.argv[1])

    r = requests.post(url, data=json.dumps(today_schedule))
    print(r.status_code)
