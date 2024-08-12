from fastapi import WebSocket
from typing import Dict
from datetime import datetime, timedelta
import pytz
from database.database import database
from psycopg.rows import dict_row
from websocket.manager import manager

async def ReAuth(ws: WebSocket, user_id: str, data: Dict):
    """
    アクセストークンの有効期限が切れた場合に再認証を行う
    """
    def msg_key_check(data: Dict):
        content = data["content"]
        if (not "access_token" in content.keys() or
            not "device_id" in content.keys()):
            raise KeyError

    try:
        msg_key_check(data)
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-ReAuth","content":{"message":"Invalid message format"}}, ws)
        return
    user = []
    access_token = []
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                if data["content"]["access_token"] == None or data["content"]["access_token"] == "":
                    raise Exception
                user = database.fetch(cursor,"users", {"access_token": data["content"]["access_token"]})
                access_token = database.fetch(cursor,"access_tokens", {"access_token": data["content"]["access_token"]})
    except Exception as e:
        print(f"Error fetching user data: {e}")
        await manager.send_personal_message({"id":data["id"],"type":"reply-ReAuth","content":{"message":"Error fetching user data"}}, ws)
        return
    
    if access_token == [] or user == []:
        await manager.send_personal_message({"id":data["id"],"type":"reply-ReAuth","content":{"message":"access_token not found"}}, ws)
        return
    
    #アクセストークンの有効期限の確認
    if not pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9) < access_token[0]["created_at"]+timedelta(hours=access_token[0]["validity_hours"]):
        await manager.send_personal_message({"id":data["id"],"type":"reply-ReAuth","content":{"message":"access_token expired"}}, ws)
        return
    
    #デバイスIDの確認(同一デバイスであるか)
    if not user[0]["device_id"] == data["content"]["device_id"]:
        await manager.send_personal_message({"id":data["id"],"type":"reply-ReAuth","content":{"message":"Invalid device_id"}}, ws)
        return
    
    #認証成功
    async with manager.lock:
        manager.latest_token_valid[user_id] = pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)
    await manager.send_personal_message({"id":data["id"],"type":"reply-ReAuth","content":{"message":"ReAuth success"}}, ws)
