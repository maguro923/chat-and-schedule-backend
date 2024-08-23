from fastapi import WebSocket
from typing import Dict
from database.database import database
from psycopg.rows import dict_row
from websocket.manager import manager
from firebase_admin import messaging
from uuid import uuid4
import os
import shutil
from datetime import datetime, timedelta
import pytz

async def JoinRoom(ws: WebSocket, user_id: str, data: Dict):
    """
    ルームへの参加リクエストを処理する
    """
    def msg_key_check(data: Dict):
        content = data["content"]
        if (not "roomid" in content.keys()):
            raise KeyError
        
    async def join_fcm_topic(fcm_token: str, roomid: str):
        """
        FCMトピックに参加する
        """
        try:
            registration_tokens = []
            if not fcm_token == None and not fcm_token == "":
                registration_tokens.append(fcm_token)
                response = messaging.subscribe_to_topic(registration_tokens, roomid)
        except Exception as e:
            print(f"Error subscribing to topic: {e}")
            raise e
    
    try:
        msg_key_check(data)
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-JoinRoom","content":{"message":"Invalid message format"}}, ws)
        return
    
    msg_id = str(uuid4())
    room_participants = []
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                room_participants = database.fetch(cursor,"room_participants", {"id":data["content"]["roomid"]})
                #ルームが存在しない場合
                if room_participants == []:
                    await manager.send_personal_message({"id":data["id"],"type":"reply-JoinRoom","content":{"message":"Room not found"}}, ws)
                    return
                
                #既に参加している場合
                is_joined = False
                for participant in room_participants:
                    if user_id == str(participant["user_id"]):
                        is_joined = True
                        break
                if is_joined:
                    await manager.send_personal_message({"id":data["id"],"type":"reply-JoinRoom","content":{"message":"Already joined"}}, ws)
                    return
                
                #参加メッセージの保存
                cursor.execute("BEGIN")
                if not database.insert(cursor,"room_participants", {"id":data["content"]["roomid"],"user_id":user_id}):
                    raise Exception
                user_data = database.fetch(cursor,"users", {"id":user_id})
                join_message = f"{user_data[0]['name']} が参加しました"
                if not database.insert(cursor,"messages", {"id":msg_id,"room_id":data["content"]["roomid"],"type":"system","content":join_message}):
                    raise Exception
                
                #FCMのトピックに参加
                try:
                    await join_fcm_topic(user_data[0]["fcm_token"],data["content"]["roomid"])
                except Exception as e:
                    print(f"Error subscribing to topic: {e}")
                    raise e
                
                #ユーザーが参加したことをルームに送信
                try:
                    for participant in room_participants:
                        async with manager.lock:
                            if not str(participant["user_id"]) == user_id and str(participant["user_id"]) in manager.active_users_id:
                                await manager.send_personal_message(
                                    {"type":"ReceiveMessage",
                                     "content":{
                                        "id":msg_id,
                                        "roomid":data["content"]["roomid"],
                                        "type":"system",
                                        "message":join_message,
                                        "created_at":str(pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9))}},
                                    manager.active_connections[str(participant["user_id"])])
                except Exception as e:
                    print(f"Error sending join message: {e}")
                    raise e
                await manager.send_personal_message({"id":data["id"],"type":"reply-JoinRoom","content":{"message":"Room joined"}}, ws)
                conn.commit()
    except Exception as e:
        print(f"Error joining room: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        await manager.send_personal_message({"id":data["id"],"type":"reply-JoinRoom","content":{"message":"Error joining room"}}, ws)
        return

async def CreateRoom(ws: WebSocket, user_id: str, data: Dict):
    """
    ルームの作成リクエストを処理する
    """
    def msg_key_check(data: Dict):
        content = data["content"]
        if (not "roomname" in content.keys()
            or not "participants" in content.keys()):
            raise KeyError
        
    async def check_is_friend():
        """
        参加者が友達か確認する
        """
        participants = data["content"]["participants"]
        try:
            with database.get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    for join_user_id in participants:
                        try:
                            is_friend = database.fetch(cursor,"friendships", {"id": user_id, "friend_id": join_user_id})
                            if is_friend == []:
                                raise PermissionError
                        except PermissionError:
                            await manager.send_personal_message({"id":data["id"],"type":"reply-CreateRoom","content":{"message":"participants must be friend"}}, ws)
                            raise PermissionError
                        except Exception as e:
                            print(f"Error checking is friend: {e}")
                            raise Exception
        except PermissionError:
            raise Exception
        except Exception as e:
            print(f"Error checking is friend: {e}")
            await manager.send_personal_message({"id":data["id"],"type":"reply-CreateRoom","content":{"message":"Error checking is friend"}}, ws)
            raise e
        
    async def get_fcm_token(userid) -> list[str]:
        """
        ユーザーIDからFCMトークンを取得する
        """
        fcm_tokens = []
        participants = data["content"]["participants"]
        participants.append(userid)
        try:
            with database.get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    for participant_id in participants:
                        try:
                            fcm_token = database.fetch(cursor,"users", {"id": participant_id})[0]["fcm_token"]
                            if not fcm_token == None and not fcm_token == "":
                                fcm_tokens.append(fcm_token)
                        except Exception as e:
                            print(f"Error fetching user data: {e}")
                            raise e
        except Exception as e:
            print(f"Error fetching user data: {e}")
            await manager.send_personal_message({"id":data["id"],"type":"reply-CreateRoom","content":{"message":"Error fetching user data"}}, ws)
            return
        return fcm_tokens
    
    try:
        msg_key_check(data)
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-CreateRoom","content":{"message":"Invalid message format"}}, ws)
        return

    try:
        await check_is_friend()
    except Exception as e:
        return
    
    #ルームの作成
    roomid = str(uuid4())
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("BEGIN")
                if not database.insert(cursor,"rooms", {"id":roomid,"name":data["content"]["roomname"]}):
                    raise Exception
                if not database.insert(cursor,"room_participants", {"id":roomid,"user_id":user_id}):
                    raise Exception
                for join_user_id in data["content"]["participants"]:
                    if not database.insert(cursor,"room_participants", {"id":roomid,"user_id":join_user_id}):
                        raise Exception    
                    #FCMのトピックを生成
                try:
                    registration_tokens = await get_fcm_token(user_id)
                    if not registration_tokens == []:
                        response = messaging.subscribe_to_topic(registration_tokens, roomid)
                    await manager.send_personal_message({"id":data["id"],"type":"reply-CreateRoom","content":{"message":"Room created","room_id":roomid}}, ws)
                except Exception as e:
                    print(f"Error subscribing to topic: {e}")
                    raise e
                
                conn.commit()
    except Exception as e:
        print(f"Error creating room: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        await manager.send_personal_message({"id":data["id"],"type":"reply-CreateRoom","content":{"message":"Error creating room"}}, ws)
        return

async def LeaveRoom(ws: WebSocket, user_id: str, data: Dict):
    """
    ルームからの退出リクエストを処理する
    """
    def msg_key_check(data: Dict):
        content = data["content"]
        if (not "roomid" in content.keys()):
            raise KeyError
    
    async def leave_fcm_topic(fcm_token: str, roomid: str):
        """
        FCMトピックから退出する
        """
        try:
            registration_tokens = []
            if not fcm_token == None and not fcm_token == "":
                registration_tokens.append(fcm_token)
                response = messaging.unsubscribe_from_topic(registration_tokens, roomid)
        except Exception as e:
            print(f"Error unsubscribing from topic: {e}")
            raise e

    try:
        msg_key_check(data)
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-LeaveRoom","content":{"message":"Invalid message format"}}, ws)
        return
    
    room_participants = []
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                room_participants = database.fetch(cursor,"room_participants", {"id":data["content"]["roomid"]})
                #ルームが存在しない場合
                if room_participants == []:
                    await manager.send_personal_message({"id":data["id"],"type":"reply-LeaveRoom","content":{"message":"Room not found"}}, ws)
                    return
                cursor.execute("BEGIN")
                if not database.delete(cursor,"room_participants", {"id":data["content"]["roomid"],"user_id":user_id}):
                    raise Exception
                #FCMのトピックから削除
                user_data = database.fetch(cursor,"users", {"id":user_id})
                await leave_fcm_topic(user_data[0]["fcm_token"],data["content"]["roomid"])
                #ルームに誰もいない場合はルームを削除
                if len(room_participants) == 1:
                    if (not database.delete(cursor,"rooms", {"id":data["content"]["roomid"]}) or
                        not database.delete(cursor,"messages", {"room_id":data["content"]["roomid"]})):
                        raise Exception
                    if os.path.isdir(f"../avatars/rooms/{data["content"]["roomid"]}"):
                        shutil.rmtree(f"../avatars/rooms/{data["content"]["roomid"]}")
                    await manager.send_personal_message({"id":data["id"],"type":"reply-LeaveRoom","content":{"message":"Delete Room"}}, ws)
                else:
                    #ユーザーに退出を送信
                    left_message = f"{user_data[0]["name"]} が退出しました"
                    database.insert(cursor,"messages", {"id":uuid4(),"room_id":data["content"]["roomid"],"type":"system","content":left_message})
                    try:
                        for participant in room_participants:
                            async with manager.lock:
                                if not str(participant["user_id"]) == user_id and (str(participant["user_id"])) in manager.active_users_id:
                                    await manager.send_personal_message(
                                        {"type":"ReceiveMessage",
                                         "content":{
                                            "roomid":data["content"]["roomid"],
                                            "type":"system",
                                            "message":left_message}},
                                        manager.active_connections[str(participant["user_id"])])
                    except Exception as e:
                        print(f"Error sending leave message: {e}")
                        raise e
                    await manager.send_personal_message({"id":data["id"],"type":"reply-LeaveRoom","content":{"message":"Room left"}}, ws)
                conn.commit()
    except Exception as e:
        print(f"Error leaving room: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        await manager.send_personal_message({"id":data["id"],"type":"reply-LeaveRoom","content":{"message":"Error leaving room"}}, ws)
        return
