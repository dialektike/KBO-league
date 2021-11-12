import ast
import json
import configparser

config = configparser.ConfigParser()
config.read("kbo_data.ini", encoding="utf-8")
kbo_data_seasons = config["seasons"]
kbo_data_seasons_list = [item for item in kbo_data_seasons]


def game_data():
    total = []

    for seasons_item in kbo_data_seasons_list:
        for item in ast.literal_eval(kbo_data_seasons[seasons_item]):
            temp_location = "data/game/" + seasons_item + "/" + seasons_item + "_" + item + ".json"
            print(temp_location)
            with open(temp_location, 'r') as json_file:
                temp = json.load(json_file)
                for item in temp:
                    total.append(item)
    return total
