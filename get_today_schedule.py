"""오늘 경기 일정을 가져오는 모듈

네이버에서 오늘 경기를 가져오는 모듈입니다.

Example:
    아래와 같이 실행하면, `04_06_Schedule.json`과 같은 이름으로 
    파일을 만들어 줍니다.

        $ python get_today_schedule_for_request.py

TODO:
    - 현재 파일을 만들고 있지만, 그냥 함수로 만들어서
      경기 자료를 바로 받아올 수 있게 바꾸면 될 것 같습니다.

"""

import configparser
import json
from datetime import date

import requests
from bs4 import BeautifulSoup


def chang_name_into_id_2021(team_name):
    """2021년용 팀 이름을 팀 ID로 바꾸는 함수

    2021년 SSG가 창단했다. 그래서 팀명이 SK에서 SSG로 변경되었다.
    그러나 KBO 홈피에서 사용하는 ID는 안 바꾼 것 같다.
    그래서 팀명을 KBO에서 바꾸는 함수를 새로 만들었다.

    Args:
        team_name (str): 팀명
    
    """
    
    list = {'KIA':'HT', '두산':'OB', '롯데':'LT', \
            'NC':'NC', 'SSG':'SK', 'LG':'LG', \
            '넥센': 'WO','키움':'WO', '히어로즈':'WO', '우리':'WO', \
            '한화':'HH', '삼성': 'SS','KT':'KT'}

    return list[team_name]

if __name__ == "__main__":

    config = configparser.ConfigParser()
    config.read("config.ini")
    temp_url = config["DEFAULT"]["naver_KBO_URL"]
    req = requests.get(temp_url)
    print(req.status_code)
    html = req.text

    exporting_dict = {}

    soup = BeautifulSoup(html, "lxml")

    exporting_dict = {}

    # 우선 현재 가져온 자료를 날짜를 찾는다.
    temp_date = soup.find("li", role="presentation", class_="on").find("em").text
    exporting_dict["date"] = temp_date
    
    # 현재년도를 가져온다.
    today = date.today()
    
    # 다음으로 게임 상대를 찾는다.
    todaySchedule = soup.find_all("ul", id="todaySchedule")
    temp_todaySchedule = todaySchedule[0]

    i = 0
    for item in temp_todaySchedule.find_all("li"):
        i = i + 1
        temp_list = {
            "away":
            chang_name_into_id_2021(
                item.find("div", class_="vs_lft").find_all("strong")[0].text
            ),
            "home":
            chang_name_into_id_2021(
                item.find("div", class_="vs_rgt").find_all("strong")[0].text
            ),
            "state":
            item.find("div", class_="vs_cnt").find_all("em", class_="state")[0].text.strip()
        }
        exporting_dict[i] = temp_list
    
    print(exporting_dict)
    
    file_name = str(today.year) + temp_date.replace(".", "_") + "_Schedule.json"
    
    with open(file_name, "w") as outfile:
        json.dump(exporting_dict, outfile)
