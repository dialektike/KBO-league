import ast
import json
import configparser
import os

import settings

_config = configparser.ConfigParser()
_config.read(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "kbo_data.ini"),
    encoding="utf-8",
)
_seasons = _config["seasons"]


def game_data(base_dir=None):
    """kbo_data.ini에 등록된 연도의 전체 경기 데이터를 로드합니다.

    Args:
        base_dir (str): 데이터 루트 디렉토리 (None이면 config.ini 설정값 사용)

    Returns:
        list: 전체 경기 데이터 목록
    """
    if base_dir is None:
        base_dir = settings.BASE_DIR

    total = []
    for year in _seasons:
        for month in ast.literal_eval(_seasons[year]):
            file_path = os.path.join(
                base_dir, "data", "game", year, f"{year}_{month}.json"
            )
            print(file_path)
            with open(file_path, "r", encoding="utf-8") as f:
                games = json.load(f)
                total.extend(games)
    return total
