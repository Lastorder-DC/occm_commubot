from datetime import datetime, timedelta, timezone
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

def convert_time_to_readable(timestr):
    # 주어진 문자열을 datetime 객체로 변환
    input_datetime = datetime.strptime(timestr, "%Y-%m-%dT%H:%M:%SZ")
    
    # 시간대를 GMT+9로 변경
    gmt9_timezone = timezone(timedelta(hours=9))
    input_datetime = input_datetime.replace(tzinfo=timezone.utc).astimezone(gmt9_timezone)
    
    # 변경된 datetime 객체를 원하는 형식의 문자열로 변환
    output_string = input_datetime.strftime("%Y년 %m월 %d일 %p %I시")
    output_string = output_string.replace("AM", "오전")
    output_string = output_string.replace("PM", "오후")
    
    return output_string

# 해당 스케줄에서 vsStages와 vsRule 추출
def extract_info(type, schedule, locale_db, fest_schedule=None):
    vs_stages = []
    vs_images = []
    vs_rule = None

    if type == "EVENT" and schedule is None:
        vs_rule = {
                "type": None,
                "rules": None
            }

    # 페스티벌중 레귤러 매치, x매치 미진행
    if type == "REGULAR" and schedule["regularMatchSetting"] is None:
        return vs_stages, vs_images, vs_rule
    if type == "X" and schedule["xMatchSetting"] is None:
        return vs_stages, vs_images, vs_rule
        
    # 페스티벌중 오픈, 챌린지
    if type in ["CHALLENGE", "OPEN"] and schedule["bankaraMatchSettings"] is None:
        if type == "OPEN":
            type = "REGULAR"
        if fest_schedule:
            for fest_match_setting in fest_schedule["festMatchSettings"]:
                if fest_match_setting["festMode"] == type:
                    vs_stages = [get_stage_name(locale_db, stage["id"]) for stage in fest_match_setting["vsStages"]]
                    vs_images = [stage["image"]["url"] for stage in fest_match_setting["vsStages"]]
                    vs_rule = get_rules_name(locale_db, fest_match_setting["vsRule"]["id"])
                    break
        return vs_stages, vs_images, vs_rule
    
    if type == "REGULAR":
        vs_stages = [get_stage_name(locale_db, stage["id"]) for stage in schedule["regularMatchSetting"]["vsStages"]]
        vs_images = [stage["image"]["url"] for stage in schedule["regularMatchSetting"]["vsStages"]]
        vs_rule = get_rules_name(locale_db, schedule["regularMatchSetting"]["vsRule"]["id"])
    if schedule and "bankaraMatchSettings" in schedule:
        for bankara_match_setting in schedule["bankaraMatchSettings"]:
            if bankara_match_setting["bankaraMode"] != type:
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
        if schedule["setting"]["__typename"] == "CoopBigRunSetting":
            vs_type = "big_run"
        elif schedule["setting"]["__typename"] == "CoopTeamContestSetting":
            vs_type = "team_contest"
        else:
            vs_type = "regular"
        vs_rule = {
            "type": vs_type,
            "weapons": [f":WPN_{get_image_id(weapon['image']['url'])}: {get_weapon_name(locale_db, weapon['__splatoon3ink_id'])}" for weapon in schedule["setting"]["weapons"]]
        }
    if schedule and "leagueMatchSetting" in schedule:
        vs_stages = [get_stage_name(locale_db, stage["id"]) for stage in schedule["leagueMatchSetting"]["vsStages"]]
        vs_images = [stage["image"]["url"] for stage in schedule["leagueMatchSetting"]["vsStages"]]
        vs_rule = {
            "type": get_event_info(locale_db, schedule["leagueMatchSetting"]["leagueMatchEvent"]["id"]),
            "rules": get_rules_name(locale_db, schedule["leagueMatchSetting"]["vsRule"]["id"])
        }
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

def get_event_info(data, event_id):
    events_data = data.get("events", {})
    event_info = events_data.get(event_id, {})
    return event_info

def get_image_id(url):
    url_parts = url.split('/')
    file_name_with_extension = url_parts[-1]
    id, _ = os.path.splitext(file_name_with_extension)

    return id

def get_schedules(locale, target="NOW"):
    if target not in ["NOW", "NEXT", "NEXTNEXT"]:
        print(f"[WARNING] Invalid target {target}")
        target = "NOW"

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
    
    locale_db_file = LOCALE_DB_TEMPLATE.format(locale)
    locale_db = load_data_from_file(locale_db_file)

    if should_refresh_data(last_locale_refresh_time, refresh_interval):
        locale_url = f"https://splatoon3.ink/data/locale/{locale}.json"
        response = requests.get(locale_url, timeout=120, headers=headers)
        locale_db = response.json()
        save_data_to_file(locale_db_file, locale_db)

    # 현재 시간
    current_time = datetime.utcnow()

    if target == "NEXT":
        current_time = current_time + timedelta(hours=2)
    elif target == "NEXTNEXT":
        current_time = current_time + timedelta(hours=4)

    # 현재 시간에 해당하는 regularSchedules 찾기
    current_regular_schedule = None
    regular_vs_time = None
    for schedule in schedules_db["data"]["regularSchedules"]["nodes"]:
        if convert_time(schedule["startTime"]) <= current_time < convert_time(schedule["endTime"]):
            current_regular_schedule = schedule
            regular_vs_time = {
                "start": convert_time_to_readable(schedule["startTime"]),
                "end": convert_time_to_readable(schedule["endTime"])
            }
            break

    # 현재 시간에 해당하는 bankaraSchedules 찾기
    current_bankara_schedule = None
    bankara_open_vs_time = None
    for schedule in schedules_db["data"]["bankaraSchedules"]["nodes"]:
        if convert_time(schedule["startTime"]) <= current_time < convert_time(schedule["endTime"]):
            current_bankara_schedule = schedule
            bankara_challenge_vs_time = {
                "start": convert_time_to_readable(schedule["startTime"]),
                "end": convert_time_to_readable(schedule["endTime"])
            }
            bankara_open_vs_time = bankara_challenge_vs_time
            break
    
    # 페스티벌 스케쥴
    fest_schedule = None
    try:
        for schedule in schedules_db["data"]["festSchedules"]["nodes"]:
            if convert_time(schedule["startTime"]) <= current_time < convert_time(schedule["endTime"]):
                fest_schedule = schedule
                break
    except Exception:
        pass

    # 현재 시간에 해당하는 xSchedules 찾기
    current_x_schedule = None
    x_vs_time = None
    for schedule in schedules_db["data"]["xSchedules"]["nodes"]:
        if convert_time(schedule["startTime"]) <= current_time < convert_time(schedule["endTime"]):
            current_x_schedule = schedule
            x_vs_time = {
                "start": convert_time_to_readable(schedule["startTime"]),
                "end": convert_time_to_readable(schedule["endTime"])
            }
            break

    # 현재 시간에 해당하는 salmonSchedule 찾기
    current_salmon_schedule = None
    next_salmon_schedule = None
    next_next_salmon_schedule = None
    salmon_current_time = datetime.utcnow()

    regular_salmon_schedules = schedules_db["data"]["coopGroupingSchedule"]["regularSchedules"]["nodes"]
    big_run_schedules = schedules_db["data"]["coopGroupingSchedule"]["bigRunSchedules"]["nodes"]
    team_contest_schedules = schedules_db["data"]["coopGroupingSchedule"]["teamContestSchedules"]["nodes"]

    # regularSchedules와 bigRunSchedules의 노드를 합침
    combined_salmon_schedules = regular_salmon_schedules + big_run_schedules + team_contest_schedules

    # startTime을 기준으로 오름차순으로 정렬
    sorted_salmon_schedules = sorted(combined_salmon_schedules, key=lambda x: x["startTime"])

    for schedule in sorted_salmon_schedules:
        start_time = convert_time(schedule["startTime"])
        end_time = convert_time(schedule["endTime"])

        if start_time <= salmon_current_time < end_time:
            current_salmon_schedule = schedule

        if current_salmon_schedule and next_salmon_schedule is None and start_time > salmon_current_time:
            next_salmon_schedule = schedule
            continue

        if next_salmon_schedule and next_next_salmon_schedule is None and start_time > salmon_current_time:
            next_next_salmon_schedule = schedule
            break

    salmon_time = {
        "start": convert_time_to_readable(current_salmon_schedule["startTime"]),
        "end": convert_time_to_readable(current_salmon_schedule["endTime"])
    }

    next_salmon_time = {
        "start": convert_time_to_readable(next_salmon_schedule["startTime"]),
        "end": convert_time_to_readable(next_salmon_schedule["endTime"])
    }

    next_next_salmon_time = {
        "start": convert_time_to_readable(next_next_salmon_schedule["startTime"]),
        "end": convert_time_to_readable(next_next_salmon_schedule["endTime"])
    }

    # 현재 시간에 해당하는 eventSchedules 찾기
    current_event_schedule = None
    upcoming_event_schedule = None
    event_time = None
    upcoming_event_time = None
    for schedule in schedules_db["data"]["eventSchedules"]["nodes"]:
        for schedule_time in schedule["timePeriods"]:
            if convert_time(schedule_time["startTime"]) <= current_time < convert_time(schedule_time["endTime"]):
                current_event_schedule = schedule
                event_time = {
                    "start": convert_time_to_readable(schedule_time["startTime"]),
                    "end": convert_time_to_readable(schedule_time["endTime"])
                }
                break
    
    if current_event_schedule is None:
        for schedule in schedules_db["data"]["eventSchedules"]["nodes"]:
            for schedule_time in schedule["timePeriods"]:
                if convert_time(schedule_time["startTime"]) <= (current_time + timedelta(minutes=30)) < convert_time(schedule_time["endTime"]):
                    upcoming_event_schedule = schedule
                    upcoming_event_time = {
                        "start": convert_time_to_readable(schedule_time["startTime"]),
                        "end": convert_time_to_readable(schedule_time["endTime"])
                    }
                    break
    
    regular_vs_stages, regular_vs_images, regular_vs_rule = extract_info("REGULAR", current_regular_schedule, locale_db)
    bankara_challenge_vs_stages, bankara_challenge_vs_images, bankara_challenge_vs_rule  = extract_info("CHALLENGE", current_bankara_schedule, locale_db, fest_schedule)
    bankara_open_vs_stages, bankara_open_vs_images, bankara_open_vs_rule = extract_info("OPEN", current_bankara_schedule, locale_db, fest_schedule)
    x_vs_stages, x_vs_images, x_vs_rule = extract_info("X", current_x_schedule, locale_db)
    if target == "NEXT":
        salmon_stages, salmon_images, salmon_info = extract_info("SALMON", next_salmon_schedule, locale_db)
        salmon_time = next_salmon_time
    elif target == "NEXTNEXT":
        salmon_stages, salmon_images, salmon_info = extract_info("SALMON", next_next_salmon_schedule, locale_db)
        salmon_time = next_next_salmon_time
    else:
        salmon_stages, salmon_images, salmon_info = extract_info("SALMON", current_salmon_schedule, locale_db)
    event_stages, event_images, event_rule = extract_info("EVENT", current_event_schedule, locale_db)
    upcoming_event_stages, upcoming_event_images, upcoming_event_rule = extract_info("EVENT", upcoming_event_schedule, locale_db)

    event_data = None
    if event_time is not None:
        event_data = {
            "type": event_rule["type"],
            "stages": event_stages,
            "images": event_images,
            "rule": event_rule["rules"],
            "time": event_time
        }
    
    upcoming_event_data = None
    if upcoming_event_time is not None:
        upcoming_event_data = {
            "type": upcoming_event_rule["type"],
            "stages": upcoming_event_stages,
            "images": upcoming_event_images,
            "rule": upcoming_event_rule["rules"],
            "time": upcoming_event_time
        }

    current_fest = None
    next_fest = None
    if schedules_db["data"]["currentFest"] is not None:
        if schedules_db["data"]["currentFest"]["id"] == "RmVzdC1VUzpVRUEtMDAwMTM=":
            fest = {
                "title": locale_db['festivals']['JUEA-00013']['title'],
                "teams": [team['teamName'] for team in locale_db["festivals"]["JUEA-00013"]['teams']],
                "state": schedules_db["data"]["currentFest"]["state"],
                "time": {
                    "start": convert_time_to_readable(schedules_db["data"]["currentFest"]["startTime"]),
                    "end": convert_time_to_readable(schedules_db["data"]["currentFest"]["endTime"])
                }
            }
            if convert_time(schedules_db["data"]["currentFest"]["startTime"]) <= current_time < convert_time(schedules_db["data"]["currentFest"]["endTime"]):
                current_fest = fest
            else:
                next_fest = fest

    return {
        "fest": current_fest,
        "next_fest": next_fest,
        "regular": {
            "stages": regular_vs_stages,
            "images": regular_vs_images,
            "rule": regular_vs_rule,
            "time": regular_vs_time
        },
        "challenge": {
            "stages": bankara_challenge_vs_stages,
            "images": bankara_challenge_vs_images,
            "rule": bankara_challenge_vs_rule,
            "time": bankara_challenge_vs_time
        },
        "open": {
            "stages": bankara_open_vs_stages,
            "images": bankara_open_vs_images,
            "rule": bankara_open_vs_rule,
            "time": bankara_open_vs_time
        },
        "xmatch": {
            "stages": x_vs_stages,
            "images": x_vs_images,
            "rule": x_vs_rule,
            "time": x_vs_time
        },
        "salmon": {
            "type": salmon_info["type"],
            "stages": salmon_stages,
            "images": salmon_images,
            "weapons": salmon_info["weapons"],
            "time": salmon_time
        },
        "event": event_data,
        "next_event": upcoming_event_data
    }

if __name__ == '__main__':
    result = get_schedules("ko-KR")
    print(result["fest"])
    print("============")
    print(result["open"])
    print("============")
    print(result["challenge"])
    print("============")