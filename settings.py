"""설정 파일(config.ini) 로더

config.ini가 없거나 항목이 빠져 있으면 fallback 값을 사용합니다.

항목:
    BASE_DIR: 데이터 루트 디렉토리 (기본값: ".")
    DELAY: 각 요청 사이 대기 시간 (초, 기본값: 0.5)
    BACKUP_TARGET_DIR: 백업 대상 디렉토리 (기본값: 빈 문자열 = 비활성)

Example:
    >>> import settings
    >>> settings.BASE_DIR
    '.'
"""

import configparser
import os

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")

_parser = configparser.ConfigParser()
_parser.read(_CONFIG_PATH, encoding="utf-8")

BASE_DIR = _parser.get("paths", "base_dir", fallback=".")
DELAY = _parser.getfloat("network", "delay", fallback=0.5)
BACKUP_TARGET_DIR = _parser.get("backup", "target_dir", fallback="")
