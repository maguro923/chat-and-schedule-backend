from fastapi import WebSocket
from typing import Dict
from datetime import datetime, timedelta
import pytz
from database.database import database
from psycopg.rows import dict_row
from websocket.manager import manager
from firebase_admin import messaging
from uuid import uuid4


async def Focus(ws: WebSocket, user_id: str, data: Dict):
    """
    ルームへのフォーカス(画面にルームのチャットが表示されている状態)を処理する
    """
    def msg_key_check(data: Dict):
        content = data["content"]
        if (not "roomid" in content.keys()):
            raise KeyError
    
    try:
        msg_key_check(data)
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-Focus","content":{"message":"Invalid message format"}}, ws)
        return

    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                room_participants = database.fetch(cursor,"room_participants", {"id": data["content"]["roomid"]})
                if room_participants == []:
                    await manager.send_personal_message({"id":data["id"],"type":"reply-Focus","content":{"message":"Room not found"}}, ws)
                    return
                
                if user_id in manager.focus_room and manager.focus_room[user_id] == data["content"]["roomid"]:
                    print(manager.focus_room)
                    await manager.send_personal_message({"id":data["id"],"type":"reply-Focus","content":{"message":"Already focused"}}, ws)
                    return
                elif user_id in manager.focus_room and manager.focus_room[user_id] != "":
                    cursor.execute("BEGIN")
                    if not database.update(cursor,"room_participants", 
                                    {"last_viewed_at": pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)},
                                    {"id": manager.focus_room[user_id],"user_id":user_id}):
                        raise Exception
                    manager.focus_room[user_id] = data["content"]["roomid"]
                    conn.commit()
                else:
                    manager.focus_room[user_id] = data["content"]["roomid"]
                print(manager.focus_room)
                await manager.send_personal_message({"id":data["id"],"type":"reply-Focus","content":{"message":"Focused"}}, ws)
    except Exception as e:
        print(f"Error fetching room data: {e}")
        if conn:
            conn.rollback()
            print("rollback")
        await manager.send_personal_message({"id":data["id"],"type":"reply-Focus","content":{"message":"Error fetching room data"}}, ws)
        return

async def UnFocus(ws: WebSocket, user_id: str, data: Dict):
    """
    ルームからのフォーカス解除(画面にルームのチャットが表示されていない状態)を処理する
    """
    def msg_key_check(data: Dict):
        content = data["content"]
        if (not "roomid" in content.keys()):
            raise KeyError
    
    try:
        msg_key_check(data)
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-UnFocus","content":{"message":"Invalid message format"}}, ws)
        return

    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                room_participants = database.fetch(cursor,"room_participants", {"id": data["content"]["roomid"]})
                if room_participants == []:
                    await manager.send_personal_message({"id":data["id"],"type":"reply-UnFocus","content":{"message":"Room not found"}}, ws)
                    return
                
                if (user_id in manager.focus_room and manager.focus_room[user_id] == "")or(not user_id in manager.focus_room):
                    print(manager.focus_room)
                    await manager.send_personal_message({"id":data["id"],"type":"reply-UnFocus","content":{"message":"Already unfocused"}}, ws)
                    return
                elif user_id in manager.focus_room and manager.focus_room[user_id] != "":
                    cursor.execute("BEGIN")
                    if not database.update(cursor,"room_participants", 
                                    {"last_viewed_at": pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)},
                                    {"id": manager.focus_room[user_id],"user_id":user_id}):
                        raise Exception
                    manager.focus_room[user_id] = ""
                    conn.commit()
                print(manager.focus_room)
                await manager.send_personal_message({"id":data["id"],"type":"reply-UnFocus","content":{"message":"Unfocused"}}, ws)
    except Exception as e:
        print(f"Error fetching room data: {e}")
        if conn:
            conn.rollback()
            print("rollback")
        await manager.send_personal_message({"id":data["id"],"type":"reply-UnFocus","content":{"message":"Error fetching room data"}}, ws)
        return