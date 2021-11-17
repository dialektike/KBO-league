# KBO-league

KBO league 경기 일정과 경기 자료를 모으고 정리하는 프로젝트입니다. 아래 코드를 실행하시면 지금까지 수집한 모든 자료를 `game_data.json`이라는 파일로 저장합니다. 만약 저장하지 않고 사용하시려면 아래 코드에서 `json`형식으로 저장하지 않고 그냥 변수 `game_data`을 사용하시면 됩니다.

```python
import json

import get

game_data = get.game_data()

file_name = "game_data.json"

with open(file_name, "w") as outfile:
    json.dump(game_date, outfile, ensure_ascii=False)
```
