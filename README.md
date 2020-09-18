# KBO
KBO 데이터를 수집하고 저장하는 곳

## 모든 자료 합치는 방법

### 라이브러리 세팅

```python
import json
import pandas as pd
```

### 경기 일정 자료

아래 2019년 자료 합치는 방법입니다. 이를 참고하여 정리하시면 됩니다. 

```python
kbo_id_temp_3=pd.read_csv("./data/temp_schedule_2019_3.csv")
kbo_id_temp_4=pd.read_csv("./data/temp_schedule_2019_4.csv")
kbo_id_temp_5=pd.read_csv("./data/temp_schedule_2019_5.csv")
kbo_id_temp_6=pd.read_csv("./data/temp_schedule_2019_6.csv")
kbo_id_temp_7=pd.read_csv("./data/temp_schedule_2019_7.csv")
kbo_id_temp_8=pd.read_csv("./data/temp_schedule_2019_8.csv")
kbo_id_temp_9=pd.read_csv("./data/temp_schedule_2019_9.csv")
kbo_id_temp_10=pd.read_csv("./data/temp_schedule_2019_10.csv")

frames = [kbo_id_temp_3, kbo_id_temp_4, kbo_id_temp_5, kbo_id_temp_6, kbo_id_temp_7, kbo_id_temp_8, kbo_id_temp_9, kbo_id_temp_10]

kbo_id_full = pd.concat(frames)
kbo_id_full = kbo_id_full.reset_index(drop=True)
kbo_id_full.to_csv("data/temp_schedule_2019.csv", index = False)
```

### 경기 자료 합치는 법

아래와 같은 방법을 시즌시작하는 월부터 정규시즌 끝까지 합니다.

```python
file_name = "data/temp_data_2019_10.json"

with open(file_name) as json_file:
    temp_data_2019_10 = json.load(json_file)
```

위에서 연 모든 파일을 다 `temp_data_2019_10`와 같이 반복해서 저장합니다.

```python
temp_full = {}
temp_full.update(temp_data_2019_10)
# temp_full

temp_file_name = "./data/temp_data_2019.json"

with open(temp_file_name, 'w') as outfile:  
    json.dump(temp_full, outfile)
```
