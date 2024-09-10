from fastapi import APIRouter, HTTPException, Header, Depends
from database.database import database
import os
from datetime import datetime, timedelta
import pytz
import glob
from psycopg.rows import dict_row
from websocket.manager import manager
import asyncio
from pydantic import BaseModel

router = APIRouter()

class Request(BaseModel):
    name: str

def get_user_headers(
    device_id: str = Header(...),
    access_token: str = Header(...)
):
    if not device_id or not access_token:
        raise HTTPException(status_code=400, detail="Invalid headers")
    return {"device_id": device_id, "access_token": access_token}

@router.post("/users/{userid}", status_code=201)
def set_userinfo(body:Request, userid:str, headers:dict = Depends(get_user_headers)):
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                user = database.fetch(cursor, "users", {"id":userid})
                token = database.fetch(cursor,"access_tokens", {"access_token": headers['access_token']})
                if user == []:
                    raise HTTPException(status_code=404, detail="User not found")
                
                #パスワードの確認及びアクセストークンの有効期限の確認及びデバイスIDの確認(同一デバイスであるか)
                if (not user[0]["access_token"] == headers['access_token'] or 
                    not pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9) < token[0]["created_at"]+timedelta(hours=token[0]["validity_hours"]) or 
                    not user[0]["device_id"] == headers['device_id']):
                    raise HTTPException(status_code=401, detail="Invalid auth")
                
                cursor.execute("BEGIN")
                if not database.update(cursor, "users", {"name":body.name, "updated_at":pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)}, {"id":userid}):
                    raise Exception
                conn.commit()
                return {"detail": "infomation updated"}
    except Exception as e:
        print(f"Error saving infomation: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        raise HTTPException(status_code=500, detail="Error saving infomation")

def get_room_headers(
    device_id: str = Header(...),
    access_token: str = Header(...),
    userid: str = Header(...)
):
    if not device_id or not access_token or not userid:
        raise HTTPException(status_code=400, detail="Invalid headers")
    return {"device_id": device_id, "access_token": access_token, "userid": userid}

@router.post("/rooms/{roomid}", status_code=201)
def set_roominfo(body:Request, roomid:str, headers:dict = Depends(get_room_headers)):
    """
    アバター以外のルーム情報を更新するAPI
    """
    async def send_message_to_ws(ws, id, name, avatar_path, joined_at):
        """
        非同期的に更新されたルーム情報を送信
        """
        await manager.send_personal_message({
            "type":"UpdateRoom",
            "content":{
                "id":id,
                "name":name,
                "avatar_path":f"/avatars/rooms{avatar_path}",
                "joined_at":joined_at}},
            ws)

    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                user = database.fetch(cursor, "users", {"id":headers["userid"]})
                token = database.fetch(cursor,"access_tokens", {"access_token": headers['access_token']})
                room_participants = database.fetch(cursor, "room_participants", {"id":roomid})
                room_info = database.fetch(cursor, "rooms", {"id":roomid})
                if user == []:
                    raise HTTPException(status_code=404, detail="User not found")
                if room_participants == [] or room_info == []:
                    raise HTTPException(status_code=404, detail="Room not found")
                
                #パスワードの確認及びアクセストークンの有効期限の確認及びデバイスIDの確認(同一デバイスであるか)
                if (not user[0]["access_token"] == headers['access_token'] or 
                    not pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9) < token[0]["created_at"]+timedelta(hours=token[0]["validity_hours"]) or 
                    not user[0]["device_id"] == headers['device_id']):
                    raise HTTPException(status_code=401, detail="Invalid auth")
                #ルーム情報の更新
                cursor.execute("BEGIN")
                if not database.update(cursor, "rooms", {"name":body.name, "updated_at":pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)}, {"id":roomid}):
                    raise Exception

                #ルームに参加しているユーザーがwebsocketに接続している場合、ルーム情報を送信
                participants = []
                for participant in room_participants:
                    if not str(participant["user_id"]) == headers["userid"]:
                        participants.append({"id":str(participant["user_id"]),"joined_at":str(participant["joined_at"])})
                for participant in participants:
                    if participant["id"] in manager.active_connections:
                        friend_ws = manager.active_connections[participant["id"]]
                        asyncio.run(send_message_to_ws(friend_ws, roomid, body.name,room_info[0]["avatar_path"],participant["joined_at"]))
                
                conn.commit()
                return {"detail": "infomation updated"}
    except Exception as e:
        print(f"Error saving infomation: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        raise HTTPException(status_code=500, detail="Error saving infomation")