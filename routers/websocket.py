from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
import asyncio
import json
from config import VALIDITY_HOURS
from datetime import datetime, timedelta
import pytz

router = APIRouter()

class ConnectionManager:
    """
    websocketの接続管理を行う
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.active_users_id: List[str] = []
        self.latest_token_valid: Dict[str, datetime] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        async with self.lock:
            self.active_connections.append(websocket)
            self.active_users_id.append(user_id)
            self.latest_token_valid[user_id] = pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)

    async def disconnect(self, websocket: WebSocket, user_id: str):
        print("disconnect")
        async with self.lock:
            self.active_connections.remove(websocket)
            self.active_users_id.remove(user_id)
            del self.latest_token_valid[user_id]
        await manager.broadcast(f"Client left the chat")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: str, websocket=None):
        for connection in self.active_connections:
            if websocket != None and connection == websocket:
                continue
            await connection.send_json(message)


manager = ConnectionManager()

async def check_token(ws: WebSocket, user_id: str):
    """
    アクセストークンの有効期限を確認し、有効期限が切れた場合に切断する
    """
    while True:
        print(f"Token check: {user_id}", manager.latest_token_valid[user_id],"{}h".format(VALIDITY_HOURS["access_token"]))
        await asyncio.sleep(VALIDITY_HOURS["access_token"]*3600-600)
        await manager.send_personal_message({"message":"Your access token has expired after 10 minutes. Please refresh access token."},ws)
        await asyncio.sleep(600)
        if pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9) > manager.latest_token_valid[user_id] + timedelta(hours=VALIDITY_HOURS["access_token"]):
            print(f"Token expired: {user_id}")
            raise WebSocketDisconnect


async def send_msg(ws: WebSocket, user_id: str):
    """
    メッセージの送信を行う
    """
    while True:
        message = {"message":f"Hello, {user_id}!","join_user":manager.active_users_id}
        await manager.send_personal_message(message, ws)
        await asyncio.sleep(360)

async def recv_msg(ws: WebSocket, user_id: str, tg: asyncio.TaskGroup):
    """
    メッセージの受信及び形式の確認等を行う
    """
    while True:
        try:
            print(f"waitng for message from {user_id}")
            data = await ws.receive_text()
            data = json.loads(data)
            print(f"received message from {user_id}:",data)
            message = {"message":data,"join_user":manager.active_users_id}
            await manager.send_personal_message(message, ws)
        except WebSocketDisconnect:
            raise WebSocketDisconnect
        except json.decoder.JSONDecodeError as e:
            print("Error: Json decode error")
            pass
        except Exception as e:
            print(f"Error: {e}",type(e))
            return

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(ws: WebSocket, user_id: str):
    await manager.connect(ws, user_id)
    try:
        async with asyncio.TaskGroup() as tg:
            CheckToken = tg.create_task(check_token(ws, user_id))
            Send = tg.create_task(send_msg(ws, user_id))
            Recv = tg.create_task(recv_msg(ws, user_id, tg))
    except* WebSocketDisconnect as e:
        print("ERROR:",e)
        await manager.disconnect(ws, user_id)