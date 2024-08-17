from fastapi import APIRouter, WebSocket
from typing import List, Dict
import asyncio
from datetime import datetime, timedelta
import pytz

router = APIRouter()

class ConnectionManager:
    """
    websocketの接続管理を行う
    """
    def __init__(self):
        self.active_connections: Dict[str,WebSocket] = {}
        self.active_users_id: List[str] = []
        self.focus_room: Dict[str, str] = {}
        self.latest_token_valid: Dict[str, datetime] = {}
        self.friend_requests: Dict[str, str] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
    
    async def verified_connect(self, websocket: WebSocket, user_id: str):
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
