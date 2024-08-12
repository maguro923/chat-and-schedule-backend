from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
import asyncio
import json
from config import VALIDITY_HOURS
from datetime import datetime, timedelta
import pytz
from database.database import database
from psycopg.rows import dict_row
from uuid import uuid4

router = APIRouter()

class ConnectionManager:
    """
    websocketの接続管理を行う
    """
    def __init__(self):
        self.active_connections: Dict[str,WebSocket] = {}
        self.active_users_id: List[str] = []
        self.latest_token_valid: Dict[str, datetime] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        async with self.lock:
            self.active_connections[user_id] = websocket
            self.active_users_id.append(user_id)
            self.latest_token_valid[user_id] = pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)

    async def disconnect(self, websocket: WebSocket, user_id: str):
        print("disconnect")
        async with self.lock:
            if user_id in self.active_connections:
                del self.active_connections[user_id]
            if user_id in self.active_users_id:
                self.active_users_id.remove(user_id)
            if user_id in self.latest_token_valid:
                del self.latest_token_valid[user_id]
        try:
            await websocket.close()
        except Exception as e:
            pass

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_json(message)

manager = ConnectionManager()

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
                await manager.send_personal_message({
                    "type":"ReceiveMessage",
                    "content":{
                        "roomid":data["content"]["roomid"],
                        "sender_id":user_id,
                        "type":data["content"]["type"]
                    }},
                    manager.active_connections[str(participant["user_id"])])
            elif not str(participant["user_id"]) == user_id:
                #送信先のユーザーが接続中でない場合
                print(f"User {participant['user_id']} is not connected")
        except Exception as e:
            print(f"Error sending message: {e}")
            pass
    
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

async def check_token(ws: WebSocket, user_id: str):
    """
    アクセストークンの有効期限を確認し、有効期限が切れた場合に切断する
    """
    while True:
        print(f"Token check: {user_id}", manager.latest_token_valid[user_id],"{}h".format(VALIDITY_HOURS["access_token"]))
        await asyncio.sleep(VALIDITY_HOURS["access_token"]*3600-600)
        await manager.send_personal_message({"type":"AuthInfo","content":{"message":"Your access token has expired after 10 minutes. Please refresh access token."}},ws)
        await asyncio.sleep(600)
        if pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9) > manager.latest_token_valid[user_id] + timedelta(hours=VALIDITY_HOURS["access_token"]):
            print(f"Token expired: {user_id}")
            raise WebSocketDisconnect

async def recv_msg(ws: WebSocket, user_id: str, tg: asyncio.TaskGroup):
    """
    メッセージの受信及び形式の確認等を行う
    """
    def msg_key_check(data: Dict):
        if (not "id" in data.keys() or
            not "type" in data.keys() or
            not "content" in data.keys()):
            raise KeyError

    while True:
        try:
            print(f"waitng for message from {user_id}")
            raw_data = await ws.receive_text()
            data = json.loads(raw_data)
            msg_key_check(data)
            if data["type"] == "ReAuth":
                tg.create_task(ReAuth(ws, user_id, data))
            elif data["type"] == "SendMessage":
                tg.create_task(SendMessage(ws, user_id, data))
            else:
                await manager.send_personal_message({"id":data["id"],"type":f"reply-{data['type']}","content":{"message":"Invalid message type"}}, ws)
        except WebSocketDisconnect:
            raise WebSocketDisconnect
        except json.JSONDecodeError:
            #key-errorに対するエラーハンドリング
            try:
                await manager.send_personal_message({"type":f"reply-{data['type']}","content":{"message":"Invalid message format"}}, ws)
            except Exception as e:
                await manager.send_personal_message({"type":"Error","content":{"message":"Invalid message format"}},ws)
            pass
        except KeyError:
            #key-errorに対するエラーハンドリング
            try:
                await manager.send_personal_message({"type":f"reply-{data['type']}","content":{"message":"Invalid json key"}}, ws)
            except Exception as e:
                await manager.send_personal_message({"type":"Error","content":{"message":"Invalid json key"}},ws)
            pass
        except Exception as e:
            print(f"Error: {e}",type(e))
            raise e

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(ws: WebSocket, user_id: str):
    await manager.connect(ws, user_id)
    try:
        async with asyncio.TaskGroup() as tg:
            CheckToken = tg.create_task(check_token(ws, user_id))
            Recv = tg.create_task(recv_msg(ws, user_id, tg))
    except* WebSocketDisconnect:
        await manager.disconnect(ws, user_id)
    except* Exception as e:
        print("ERROR:",repr(e))
        await manager.disconnect(ws, user_id)