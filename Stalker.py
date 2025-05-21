import requests
import os
import time
from datetime import datetime
from dotenv import load_dotenv
import json

load_dotenv()

USER_ID = os.getenv("TARGET_USER_ID")
COOKIE_PATH = os.getenv("VRCHAT_COOKIE_PATH")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
LOG_FILE = "vrchat_status_log.txt"

WANTED_KEYS = [
    "bio",
    "bioLinks",
    "displayName",
    "last_activity",
    "last_login",
    "last_platform",
    "location",
    "pronouns",
    "state",
    "statusDescription",
    "travelingToInstance",
    "travelingToLocation",
    "travelingToWorld"
]

previous_world = None
previous_data = {}
first_run = True

def load_cookies_from_file(path: str) -> dict:
    cookies = {}
    try:
        with open(path, "r") as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    cookies[key.strip()] = value.strip()
    except FileNotFoundError:
        print(f"cookieが見つかりません: {path}")
    return cookies

def fetch_user_data(user_id: str, cookies: dict) -> dict:
    url = f"https://vrchat.com/api/1/users/{user_id}"
    headers = {'user-agent': "VRChatAPI-Python-Client/1.19.2/python"}
    response = requests.get(url, cookies=cookies, headers=headers)
    if response.status_code == 429:
        print("⚠️ VRChat API制限中（ユーザーデータ）: ステータスコード 429 - Too Many Requests")
        time.sleep(30)
        return fetch_user_data(user_id, cookies)
    if response.status_code != 200:
        raise Exception(f"APIリクエスト失敗: {response.status_code} {response.text}")
    return response.json()

def fetch_world_info(world_id: str, cookies: dict) -> dict:
    if not world_id:
        return {}
    url = f"https://vrchat.com/api/1/worlds/{world_id}"
    headers = {'user-agent': "VRChatAPI-Python-Client/1.19.2/python"}
    response = requests.get(url, cookies=cookies, headers=headers)
    if response.status_code == 429:
        print("⚠️ VRChat API制限中（ワールドデータ）: ステータスコード 429 - Too Many Requests")
        time.sleep(30)
        return fetch_world_info(world_id, cookies)
    if response.status_code != 200:
        return {}
    return response.json()

def extract_wanted_data(data: dict, keys: list) -> dict:
    return {key: data.get(key) for key in keys}

def extract_world_id_from_location(location_str: str) -> str:
    if not location_str:
        return ""
    parts = location_str.split(":", 1)[0]
    if parts.startswith("wrld_"):
        return parts
    return ""

def location_type_label(location_str: str) -> str:
    if not location_str:
        return "不明"
    if "private" in location_str:
        return "Private"
    if "~group(" in location_str:
        if "~groupAccessType(public)" in location_str:
            return "GroupPublic"
        if "~groupAccessType(plus)" in location_str:
            return "Group+"
        if "~groupAccessType(members)" in location_str:
            return "Group"
        return "不明"
    if "~hidden(" in location_str:
        return "Friend+"
    if "~friends(" in location_str:
        return "Friend"
    if location_str.startswith("wrld_"):
        return "Public"
    return "不明"

def get_my_instance_id(user_data):
    instance_full = user_data.get("travelingToInstance") or ""
    if instance_full:
        return instance_full

    location = user_data.get("location") or ""
    if ":" in location:
        instance_part = location.split(":", 1)[1]
        return instance_part

    return ""

def log_event(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp} {message}"
    send_webhook(log_line)
    print(log_line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

def lists_differ(l1, l2):
    return json.dumps(l1, sort_keys=True) != json.dumps(l2, sort_keys=True)

def monitor_loop():
    global previous_world, previous_data, first_run

    if not USER_ID or not COOKIE_PATH:
        print("環境変数 'TARGET_USER_ID' または 'VRCHAT_COOKIE_PATH' が未設定です。設定してください。")
        return

    cookies = load_cookies_from_file(COOKIE_PATH)
    if not cookies:
        print("クッキーの読み込みに失敗しました。正しいファイルパスを指定してください。")
        return

    while True:
        try:
            user_data_full = fetch_user_data(USER_ID, cookies)
            user_data = extract_wanted_data(user_data_full, WANTED_KEYS)
            display_name = user_data.get("displayName", "Unknown")

            current_world = user_data.get("travelingToWorld") or user_data.get("location") or ""
            current_world_id = extract_world_id_from_location(current_world)
            current_location_type = location_type_label(current_world)
            new_status = user_data_full.get("status")
            old_status = previous_data.get("status")
            previous_state = previous_data.get("state")
            current_state = user_data.get("state")
            if first_run:
                previous_data = user_data
                previous_world = current_world
                first_run = False

                world_info = fetch_world_info(current_world_id, cookies) if current_world_id else {}
                world_name = world_info.get("name", "Private")
                state = user_data.get("state")

                if state == "offline":
                    log_event(f"{display_name} は現在オフラインです")
                elif state == "active":
                    log_event(f"{display_name} は現在アクティブです")
                elif state == "online":
                    log_event(f"{display_name} は現在オンラインです")
                    log_event(f"{display_name} は「{world_name}」にいます（type: {current_location_type}）")
                else:
                    log_event(f"{display_name} の状態は不明です: {state}")
                time.sleep(5)
                continue

            if current_state != previous_state:
                if current_state == "offline":
                    log_event(f"{display_name} はオフラインになりました")
                elif current_state == "active":
                    log_event(f"{display_name} はアクティブになりました")
                elif current_state == "online":
                    log_event(f"{display_name} はオンラインになりました")
            if user_data.get("displayName") != previous_data.get("displayName"):
                log_event(f"ユーザー名が変更されました: 「{previous_data.get('displayName')}」→「{user_data['displayName']}」")

            if user_data.get("bio") != previous_data.get("bio"):
                log_event(f"{display_name} の bio が変更されました: 「{previous_data.get('bio')}」→「{user_data['bio']}」")

            if lists_differ(user_data.get("bioLinks"), previous_data.get("bioLinks")):
                log_event(f"{display_name} の bioLinks が変更されました: {previous_data.get('bioLinks')} → {user_data.get('bioLinks')}")

            if user_data.get("statusDescription") != previous_data.get("statusDescription"):
                log_event(f"{display_name} のステータス説明が変わりました: 「{previous_data.get('statusDescription')}」→「{user_data['statusDescription']}」")
            if new_status is not None and old_status is not None and new_status != old_status:
                log_event(f"{display_name} のステータスが変わりました: 「{old_status}」→「{new_status}」")

            if current_world != previous_world:
                world_info = fetch_world_info(current_world_id, cookies) if current_world_id else {}
                world_name = world_info.get("name", "Private")

                if current_location_type != "不明":
                    if current_location_type == "Private":
                        log_event(f"{display_name} は「{world_name}」にいます（type: {current_location_type}）")
                    else:
                        if user_data_full.get("travelingToWorld"):
                            log_event(f"{display_name} は「{world_name}」に移動しました（type: {current_location_type}）")
                        else:
                            log_event(f"{display_name} は「{world_name}」にいます（type: {current_location_type}）")
                previous_world = current_world

            previous_data = {**user_data, "status": user_data_full.get("status")}

        except Exception as e:
            print(f"エラーが発生しました: {e}")

        time.sleep(3)

def send_webhook(content):
    requests.post(
        WEBHOOK_URL,
        json = {
            "content": f"{content} <t:{int(time.time())}:R>"
        }
    )

if __name__ == "__main__":
    monitor_loop()
