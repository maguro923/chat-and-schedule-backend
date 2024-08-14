from fastapi import  WebSocket
from typing import Dict
from database.database import database
from psycopg.rows import dict_row
from uuid import uuid4
from websocket.manager import manager
from firebase_admin import messaging

async def SendMessage(ws: WebSocket, user_id: str, data: Dict):
    """
    メッセージの送信リクエストを処理する
    """
    def msg_key_check(data: Dict, type: str):
        if type == "text":
            content = data["content"]
            if (not "message" in content.keys() or
                not "roomid" in content.keys()):
                raise KeyError
        elif type == "image":
            content = data["content"]
            if (not "image" in content.keys() or
                not "roomid" in content.keys()):
                raise KeyError
    
    def check_user_in_room(room_participants, user_id: str):
        """
        リクエストしたユーザーがルームに参加しているか確認
        """
        for participant in room_participants:
            if str(participant["user_id"]) == user_id:
                return True
        return False

    try:
        if not "type" in data["content"].keys():
            raise KeyError
        msg_key_check(data, data["content"]["type"])
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-SendMessage","content":{"message":"Invalid message format"}}, ws)
        return
    
    room_participants = []
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                room_participants = database.fetch(cursor,"room_participants", {"id": data["content"]["roomid"]})
    except Exception as e:
        print(f"Error fetching room data: {e}")
        await manager.send_personal_message({"id":data["id"],"type":"reply-SendMessage","content":{"message":"Error fetching room data"}}, ws)
        return
    
    #ルームに参加しているか
    if not check_user_in_room(room_participants, user_id):
        await manager.send_personal_message({"id":data["id"],"type":"reply-SendMessage","content":{"message":"User not in room"}}, ws)
        return
    
    #メッセージの保存
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("BEGIN")
                if data["content"]["type"] == "text":
                    if not database.insert(cursor,"messages", {"id":uuid4(),"room_id":data["content"]["roomid"],"sender_id":user_id,"type":"text","content":data["content"]["message"]}):
                        raise Exception
                elif data["content"]["type"] == "image":
                    if not database.insert(cursor,"messages", {"id":uuid4(),"room_id":data["content"]["roomid"],"sender_id":user_id,"type":"image","content":data["content"]["image"]}):
                        raise Exception
                else:
                    raise Exception
                conn.commit()
    except Exception as e:
        print(f"Error saving message: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        await manager.send_personal_message({"id":data["id"],"type":"reply-SendMessage","content":{"message":"Error saving message"}}, ws)
        return
    
    #メッセージ送信成功(他ユーザーへの送信は保証しない)を通知
    await manager.send_personal_message({
        "id":data["id"],"type":"reply-SendMessage","content":{"message":"Message sent"}}
        , ws)
    
    #メッセージ送信
    for participant in room_participants:
        try:
            if str(participant["user_id"]) in manager.active_connections and not str(participant["user_id"]) == user_id:
                #送信先のユーザーが接続中の場合
                print(f"send message to {participant['user_id']}")
                msg_type = ""
                msg = ""
                if data["content"]["type"] == "text":
                    msg_type = "text"
                    msg = data["content"]["message"]
                elif data["content"]["type"] == "image":
                    msg_type = "image"
                    msg = data["content"]["image"]
                await manager.send_personal_message({
                    "type":"ReceiveMessage",
                    "content":{
                        "roomid":data["content"]["roomid"],
                        "senderid":user_id,
                        "type":data["content"]["type"],
                        msg_type:msg
                    }},
                    manager.active_connections[str(participant["user_id"])])
            elif not str(participant["user_id"]) == user_id:
                #送信先のユーザーが接続中でない場合
                print(f"{participant['user_id']} is offline")
        except Exception as e:
            print(f"Error sending message: {e}")
            pass
    try:
        bodytext = ""
        if data["content"]["type"] == "text":
            bodytext = data["content"]["message"]
        elif data["content"]["type"] == "image":
            bodytext = "写真が送信されました"
        message = messaging.Message(
            notification=messaging.Notification(
                title="新しいメッセージ",
                body=bodytext
            ),
            topic=data["content"]["roomid"]
        )
        response = messaging.send(message)
        print(response)
    except Exception as e:
        print(f"Error sending FCM notifiction: {e}")
        pass
