#!/usr/bin/python3
# -*- coding: utf-8 -*-
import re
import os
from time import sleep
from mastodon import Mastodon
from mastodon.streaming import StreamListener
from google.oauth2 import service_account
import gspread
import schedule
from pyjosa.josa import Josa
from dotenv import load_dotenv
from splatoon3 import get_schedules
load_dotenv()

salmon_typestr = {
    "regular": "",
    "big_run": "빅 런 발생!\n",
    "team_contest": "아르바이트 팀 콘테스트 진행중!\n"
}

# 구글시트 세팅
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file",
         "https://www.googleapis.com/auth/drive"]

creds = service_account.Credentials.from_service_account_file(f'{os.getcwd()}/key.json')
creds = creds.with_scopes(scope)
gc = gspread.authorize(creds)
sh = gc.open_by_url(os.getenv('SHEET_URL'))
search = sh.worksheet(os.getenv('MAIN_SHEET_NAME'))
default_visibility = os.getenv('MASTODON_DEFAULT_VISIBILITY')
admin_handle = os.getenv('BOT_ADMIN_HANDLE')
tag_admin = os.getenv('BOT_TAG_ADMIN') == 'true'
locale = os.getenv('BOT_LOCALE')
cur_schedule = get_schedules(locale)
cur_salmon = cur_schedule["salmon"]
cur_event = None
next_event = None

BASE = os.getenv('MASTODON_BASE')

m = Mastodon(
    client_id=os.getenv('MASTODON_CLIENT_ID'),
    client_secret=os.getenv('MASTODON_CLIENT_SECRET'),
    access_token=os.getenv('MASTODON_ACCESS_TOKEN'),
    api_base_url=BASE
)
bot = m.me()

print(f"성공적으로 계정 {bot.username}으로 로그인 되었습니다.")

def detect_schedule_change():
    global cur_schedule
    global cur_salmon
    global cur_event
    global next_event
    new_schedule = get_schedules(locale)

    if cur_schedule != new_schedule:
        cur_schedule = new_schedule
        m.status_post(f"""스케쥴이 업데이트되었습니다.
{cur_schedule['regular']['time']['start']} ~ {cur_schedule['regular']['time']['end']}

현재 영역배틀
맵 : {', '.join(cur_schedule['regular']['stages'])}
규칙 : {cur_schedule['regular']['rule']}

현재 카오폴리스 매치 챌린지
맵 : {', '.join(cur_schedule['challenge']['stages'])}
규칙 : {cur_schedule['challenge']['rule']}

현재 카오폴리스 매치 오픈
맵 : {', '.join(cur_schedule['open']['stages'])}
규칙 : {cur_schedule['open']['rule']}

현재 X 매치
맵 : {', '.join(cur_schedule['xmatch']['stages'])}
규칙 : {cur_schedule['xmatch']['rule']}""", visibility=default_visibility)
        
        if cur_salmon != new_schedule["salmon"]:
            cur_salmon = new_schedule["salmon"]
            m.status_post(f"""연어런 스케쥴 변경!
{cur_salmon['time']['start']} ~ {cur_salmon['time']['end']}

{salmon_typestr[cur_salmon['type']]}맵 : {''.join(cur_salmon['stages'])}
무기 : {', '.join(cur_salmon['weapons'])}""", visibility=default_visibility)
        
    if cur_event != new_schedule["event"] and new_schedule["event"] is not None:
        cur_event = new_schedule["event"]
        event_name = cur_event['type']['name']
        event_regulation = cur_event['type']['regulation'].replace('<br />', '\n')
        m.status_post(f"""이벤트 매치 진행중!
{cur_event['time']['start']} ~ {cur_event['time']['end']}

{event_name}
{event_regulation}


맵 : {', '.join(cur_event['stages'])}
규칙 : {cur_event['rule']}""", visibility=default_visibility)
    
    # 현재 이벤트중이 아니면서, 저장한 다음 이벤트가 달라졌다면 공지!
    if new_schedule["event"] is None and next_event != new_schedule["next_event"] and new_schedule["next_event"] is not None:
        next_event = new_schedule["next_event"]
        event_name = next_event['type']['name']
        event_regulation = next_event['type']['regulation'].replace('<br />', '\n')
        m.status_post(f"""30분뒤 이벤트 매치 진행 예정!
{next_event['time']['start']} ~ {next_event['time']['end']}

{event_name}
{event_regulation}


맵 : {', '.join(next_event['stages'])}
규칙 : {next_event['rule']}""", visibility=default_visibility)

schedule.every(10).seconds.do(detect_schedule_change)

CLEANR = re.compile('<.*?>')
SEC_CLEANR = re.compile('\B@\w+')

def gettext(raw_html):
    """
    주어진 문자열에서 HTML 태그 및 멘션을 제거하고 정제된 텍스트를 반환합니다.

    Parameters:
        raw_html (str): HTML 태그가 포함된 원본 문자열

    Returns:
        str: HTML 태그 및 멘션이 제거된 정제된 텍스트
    """
    cleantext = re.sub(CLEANR, '', raw_html)
    cleantext = re.sub(SEC_CLEANR, '', cleantext)
    return cleantext

def cleanhtml(raw_html):
    """
    주어진 문자열에서 HTML 태그를 제거하고 정제된 텍스트를 반환합니다.

    Parameters:
        raw_html (str): HTML 태그가 포함된 원본 문자열

    Returns:
        str: HTML 태그가 제거된 정제된 텍스트
    """
    cleantext = re.sub(CLEANR, '', raw_html)
    return cleantext

def getkey(toot_body):
    """
    주어진 문자열에서 [ ] 사이의 키워드를 추출하여 반환합니다.

    Parameters:
        toot_body (str): 키워드를 추출할 문자열

    Returns:
        str: 추출된 키워드 (만약 키워드가 없으면 None을 반환)
    """
    match = re.search(r'\[(.*?)\]', toot_body)
    return match.group(1) if match else None

class Listener(StreamListener):
    """
    Mastodon 스트리밍 API의 이벤트를 받아 처리합니다.
    """
    def on_notification(self, notification):
        """
        Mastodon 스트리밍 알림 이벤트 핸들러입니다. 언급 메시지를 처리하고 조사를 진행합니다.

        Parameters:
            notification (dict): Mastodon 알림 정보를 담은 딕셔너리
        """
        if notification['type'] == 'mention':
            got = cleanhtml(notification['status']['content'])
            keyword = getkey(got)

            # [] 미포함된 툿은 무시합니다(조사 선택지에 이어 대화하기 금지...)
            if keyword is None:
                return
            
            try:
                # 조사 시트에서 키워드를 찾는다
                look = search.find(keyword, in_column=1, case_sensitive=True).row
                result = search.get(f"R{look}C2:R{look}C5", value_render_option="UNFORMATTED_VALUE")[0]
                schedules = get_schedules(locale, "NOW")
                next_schedules = get_schedules(locale, "NEXT")
                next_next_schedules = get_schedules(locale, "NEXTNEXT")

                # 현재 스케쥴 요청
                if result[0] == "%영배%":
                    m.status_post(f"""@{notification['status']['account']['acct']} 현재 영역배틀
맵 : {', '.join(schedules['regular']['stages'])}
규칙 : {schedules['regular']['rule']}

다음 영역배틀
맵 : {', '.join(next_schedules['regular']['stages'])}
규칙 : {next_schedules['regular']['rule']}

다음다음 영역배틀
맵 : {', '.join(next_next_schedules['regular']['stages'])}
규칙 : {next_next_schedules['regular']['rule']}""", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                elif result[0] == "%챌린지%":
                    m.status_post(f"""@{notification['status']['account']['acct']} 현재 카오폴리스 매치 챌린지
맵 : {', '.join(schedules['challenge']['stages'])}
규칙 : {schedules['challenge']['rule']}

다음 카오폴리스 매치 챌린지
맵 : {', '.join(next_schedules['challenge']['stages'])}
규칙 : {next_schedules['challenge']['rule']}

다음다음 카오폴리스 매치 챌린지
맵 : {', '.join(next_next_schedules['challenge']['stages'])}
규칙 : {next_next_schedules['challenge']['rule']}""", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                elif result[0] == "%오픈%":
                    m.status_post(f"""@{notification['status']['account']['acct']} 현재 카오폴리스 매치 오픈
맵 : {', '.join(schedules['open']['stages'])}
규칙 : {schedules['open']['rule']}

다음 카오폴리스 매치 챌린지
맵 : {', '.join(next_schedules['open']['stages'])}
규칙 : {next_schedules['open']['rule']}

다음다음 카오폴리스 매치 챌린지
맵 : {', '.join(next_next_schedules['open']['stages'])}
규칙 : {next_next_schedules['open']['rule']}""", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                elif result[0] == "%엑스%":
                    m.status_post(f"""@{notification['status']['account']['acct']} 현재 X 매치
맵 : {', '.join(schedules['xmatch']['stages'])}
규칙 : {schedules['xmatch']['rule']}

다음 X 매치
맵 : {', '.join(next_schedules['xmatch']['stages'])}
규칙 : {next_schedules['xmatch']['rule']}

다음다음 X 매치
맵 : {', '.join(next_next_schedules['xmatch']['stages'])}
규칙 : {next_next_schedules['xmatch']['rule']}""", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                elif result[0] == "%연어%":
                    m.status_post(f"""@{notification['status']['account']['acct']} 현재 연어런
{salmon_typestr[schedules["salmon"]['type']]}맵 : {''.join(schedules["salmon"]['stages'])}
무기 : {', '.join(schedules["salmon"]['weapons'])}

다음 연어런
{salmon_typestr[next_schedules["salmon"]['type']]}맵 : {''.join(next_schedules["salmon"]['stages'])}
무기 : {', '.join(next_schedules["salmon"]['weapons'])}

다음다음 연어런
{salmon_typestr[next_next_schedules["salmon"]['type']]}맵 : {''.join(next_next_schedules["salmon"]['stages'])}
무기 : {', '.join(next_next_schedules["salmon"]['weapons'])}""", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                else:
                    # 조사 선택지인 경우
                    if result[1] is True:
                        try:
                            print(f"유저 {notification['status']['account']['acct']} 조건조사 진행 - {notification['status']['id']}")
                            if result[2] is True:
                                # 방문한후 지문이 입력되어 있다면 사용, 없다면 방문여부 무관 기존 지문을 재사용한다.
                                if len(result) > 3:
                                    m.status_post(f"@{notification['status']['account']['acct']} {result[3]}", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                                else:
                                    m.status_post(f"@{admin_handle} [체크 필요] 키워드 {keyword}의 방문된 후의 지문이 누락되었습니다. 조사전후 차이가 불필요한 경우 \"조사 유무 확인?\" 부분 체크를 해제해주세요.", visibility='private')
                                    m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                                return
                            else:
                                m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                                search.update_cell(look, 4, 'TRUE')
                        except Exception as exception_obj:
                            m.status_post(f"@notice@occm.cc 봇 아이디 {bot['username']}의 체크 관련 오류 발생: {exception_obj}", visibility='private')
                    # 이외(항시 가능)
                    else:
                        print(f"유저 {notification['status']['account']['acct']} 상시조사 진행 - {notification['status']['id']}")
                        m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                        # HACK : 시트상 변화가 없다면 랜덤문구가 안나오기에 시트에 영향이 없는 체크박스를 체크했다 해제한다
                        search.update_cell(look, 4, 'TRUE')
                        search.update_cell(look, 4, 'FALSE')
            except AttributeError:
                m.status_post(f"@{notification['status']['account']['acct']} [{keyword}]{Josa.get_josa(keyword, '은')} {os.getenv('MESSAGE_INVALID_KEYWORD')}", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                if tag_admin:
                    m.status_post(f"@{admin_handle} {os.getenv('MESSAGE_ADM_INVALID_KEYWORD_PRE')} {keyword}{Josa.get_josa(keyword, '이가')} {os.getenv('MESSAGE_ADM_INVALID_KEYWORD_AFR')}", visibility='private')

def main():
    """
    메인 함수로, Mastodon 스트리밍을 시작합니다.
    """
    m.stream_user(Listener(), run_async=True, reconnect_async=True, reconnect_async_wait_sec=10)
    while True:
        schedule.run_pending()
        sleep(1)

if __name__ == '__main__':
    main()
