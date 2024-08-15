from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
import asyncio
import json
from config import VALIDITY_HOURS
from datetime import datetime, timedelta
import pytz
from websocket.manager import manager
from websocket.usercheck import check_user_id, check_access_token
from websocket.reauth import ReAuth
from websocket.sendmessage import SendMessage
from websocket.room import JoinRoom, CreateRoom, LeaveRoom
from websocket.friend import Friend,UnFriend

router = APIRouter()

async def check_token_exprire(ws: WebSocket, user_id: str):
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
            elif data["type"] == "CreateRoom":
                tg.create_task(CreateRoom(ws, user_id, data))
            elif data["type"] == "JoinRoom":
                tg.create_task(JoinRoom(ws, user_id, data))
            elif data["type"] == "LeaveRoom":
                tg.create_task(LeaveRoom(ws, user_id, data))
            elif data["type"] == "Friend":
                tg.create_task(Friend(ws, user_id, data))
            elif data["type"] == "UnFriend":
                tg.create_task(UnFriend(ws, user_id, data))
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
    #ユーザーIDを確認
    is_valid_user_id,access_token = await check_user_id(ws,user_id)
    if not is_valid_user_id:
        return
    
    #アクセストークンを確認
    if not await check_access_token(ws, user_id, access_token):
        return
    
    #認証成功
    await manager.connect(ws, user_id)
    try:
        async with asyncio.TaskGroup() as tg:
            CheckToken = tg.create_task(check_token_exprire(ws, user_id))
            Recv = tg.create_task(recv_msg(ws, user_id, tg))
    except* WebSocketDisconnect:
        await manager.disconnect(ws, user_id)
    except* Exception as e:
        print("ERROR:",repr(e))
        await manager.disconnect(ws, user_id)