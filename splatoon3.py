from datetime import datetime, timedelta
import json
import os
import requests

SCHEDULES_DB_FILE = "schedules_db.json"
LOCALE_DB_TEMPLATE = "locale_{}.json"

def save_data_to_file(filename, data):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)

def load_data_from_file(filename):
    if os.path.exists(filename):
        with open(filename, "r") as file:
            return json.load(file)
    return None

def get_last_modified_time(filename):
    if os.path.exists(filename):
        return datetime.fromtimestamp(os.path.getmtime(filename))
    return None

def should_refresh_data(last_refresh_time, refresh_interval):
    if not last_refresh_time:
        return True
    current_time = datetime.utcnow()
    elapsed_time = current_time - last_refresh_time
    return elapsed_time >= refresh_interval

def convert_time(timestr):
    return datetime.strptime(timestr, '%Y-%m-%dT%H:%M:%SZ')

# 해당 스케줄에서 vsStages와 vsRule 추출
def extract_info(schedule, locale_db, type="OPEN"):
    vs_stages = []
    vs_rule = None
    if schedule and "regularMatchSetting" in schedule:
        vs_stages = [get_stage_name(locale_db, stage["id"]) for stage in schedule["regularMatchSetting"]["vsStages"]]
        vs_images = [stage["image"]["url"] for stage in schedule["regularMatchSetting"]["vsStages"]]
        vs_rule = get_rules_name(locale_db, schedule["regularMatchSetting"]["vsRule"]["id"])
    if schedule and "bankaraMatchSettings" in schedule:
        for bankara_match_setting in schedule["bankaraMatchSettings"]:
            if bankara_match_setting["mode"] != type:
                continue
            vs_stages = [get_stage_name(locale_db, stage["id"]) for stage in bankara_match_setting["vsStages"]]
            vs_images = [stage["image"]["url"] for stage in bankara_match_setting["vsStages"]]
            vs_rule = get_rules_name(locale_db, bankara_match_setting["vsRule"]["id"])
    if schedule and "leagueMatchSetting" in schedule:
        vs_stages = [get_stage_name(locale_db, stage["id"]) for stage in schedule["leagueMatchSetting"]["vsStages"]]
        vs_images = [stage["image"]["url"] for stage in schedule["leagueMatchSetting"]["vsStages"]]
        vs_rule = get_rules_name(locale_db, schedule["leagueMatchSetting"]["vsRule"]["id"])
    if schedule and "xMatchSetting" in schedule:
        vs_stages = [get_stage_name(locale_db, stage["id"]) for stage in schedule["xMatchSetting"]["vsStages"]]
        vs_images = [stage["image"]["url"] for stage in schedule["xMatchSetting"]["vsStages"]]
        vs_rule = get_rules_name(locale_db, schedule["xMatchSetting"]["vsRule"]["id"])
    if schedule and "setting" in schedule:
        vs_stages = [get_stage_name(locale_db, schedule["setting"]["coopStage"]["id"]), ]
        vs_images = [schedule["setting"]["coopStage"]["image"]["url"], ]
        vs_rule = [f":WPN_{get_image_id(weapon['image']['url'])}: {get_weapon_name(locale_db, weapon['__splatoon3ink_id'])}" for weapon in schedule["setting"]["weapons"]]
    return vs_stages, vs_images, vs_rule

def get_stage_name(data, stage_id):
    stages_data = data.get("stages", {})
    stage_info = stages_data.get(stage_id, {})
    stage_name = stage_info.get("name", None)
    return stage_name

def get_rules_name(data, rule_id):
    rules_data = data.get("rules", {})
    rule_info = rules_data.get(rule_id, {})
    rule_name = rule_info.get("name", None)
    return rule_name

def get_weapon_name(data, weapons_id):
    weapons_data = data.get("weapons", {})
    weapon_info = weapons_data.get(weapons_id, {})
    weapon_name = weapon_info.get("name", None)
    return weapon_name

def get_image_id(url):
    url_parts = url.split('/')
    file_name_with_extension = url_parts[-1]
    id, _ = os.path.splitext(file_name_with_extension)

    return id

def get_schedules(locale):
    headers = {
        'User-Agent': 'DeepCutRadio_Splat00n_ink/1.0',
        'From': 'radio@splat00n.ink'  # This is another valid field
    }
    last_schedules_refresh_time = get_last_modified_time(SCHEDULES_DB_FILE)
    last_locale_refresh_time = get_last_modified_time(LOCALE_DB_TEMPLATE.format("ko-KR"))

    refresh_interval = timedelta(hours=1)
    schedules_db = load_data_from_file(SCHEDULES_DB_FILE)
    
    if should_refresh_data(last_schedules_refresh_time, refresh_interval):
        schedules_url = "https://splatoon3.ink/data/schedules.json"
        response = requests.get(schedules_url, timeout=120, headers=headers)
        schedules_db = response.json()
        save_data_to_file(SCHEDULES_DB_FILE, schedules_db)
        last_schedules_refresh_time = datetime.utcnow()
    
    locale_db_file = LOCALE_DB_TEMPLATE.format(locale)
    locale_db = load_data_from_file(locale_db_file)

    if should_refresh_data(last_locale_refresh_time, refresh_interval):
        locale_url = f"https://splatoon3.ink/data/locale/{locale}.json"
        response = requests.get(locale_url, timeout=120, headers=headers)
        locale_db = response.json()
        save_data_to_file(locale_db_file, locale_db)
        last_locale_refresh_time = datetime.utcnow()

    # 현재 시간
    current_time = datetime.utcnow()

    # 현재 시간에 해당하는 regularSchedules 찾기
    current_regular_schedule = None
    for schedule in schedules_db["data"]["regularSchedules"]["nodes"]:
        if convert_time(schedule["startTime"]) <= current_time < convert_time(schedule["endTime"]):
            current_regular_schedule = schedule
            break

    # 현재 시간에 해당하는 bankaraSchedules 찾기
    current_bankara_schedule = None
    for schedule in schedules_db["data"]["bankaraSchedules"]["nodes"]:
        if convert_time(schedule["startTime"]) <= current_time < convert_time(schedule["endTime"]):
            current_bankara_schedule = schedule
            break

    # 현재 시간에 해당하는 xSchedules 찾기
    current_x_schedule = None
    for schedule in schedules_db["data"]["xSchedules"]["nodes"]:
        if convert_time(schedule["startTime"]) <= current_time < convert_time(schedule["endTime"]):
            current_x_schedule = schedule
            break

    # 현재 시간에 해당하는 salmonSchedule 찾기
    current_salmon_schedule = None
    for schedule in schedules_db["data"]["coopGroupingSchedule"]["regularSchedules"]["nodes"]:
        if convert_time(schedule["startTime"]) <= current_time < convert_time(schedule["endTime"]):
            current_salmon_schedule = schedule
            break
    
    # 결과 출력
    regular_vs_stages, regular_vs_images, regular_vs_rule = extract_info(current_regular_schedule, locale_db)
    bankara_challenge_vs_stages, bankara_challenge_vs_images, bankara_challenge_vs_rule  = extract_info(current_bankara_schedule, locale_db, "CHALLENGE")
    bankara_open_vs_stages, bankara_open_vs_images, bankara_open_vs_rule  = extract_info(current_bankara_schedule, locale_db, "OPEN")
    x_vs_stages, x_vs_images, x_vs_rule = extract_info(current_x_schedule, locale_db)
    salmon_stages, salmon_images, salmon_weapons = extract_info(current_salmon_schedule, locale_db)

    return {
        "regular": {
            "stages": regular_vs_stages,
            "images": regular_vs_images,
            "rule": regular_vs_rule
        },
        "challenge": {
            "stages": bankara_challenge_vs_stages,
            "images": bankara_challenge_vs_images,
            "rule": bankara_challenge_vs_rule
        },
        "open": {
            "stages": bankara_open_vs_stages,
            "images": bankara_open_vs_images,
            "rule": bankara_open_vs_rule
        },
        "xmatch": {
            "stages": x_vs_stages,
            "images": x_vs_images,
            "rule": x_vs_rule
        },
        "salmon": {
            "stages": salmon_stages,
            "images": salmon_images,
            "weapons": salmon_weapons
        }
    }

if __name__ == '__main__':
    print(get_schedules("ko-KR"))