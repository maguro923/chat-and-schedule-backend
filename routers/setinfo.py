from fastapi import APIRouter, HTTPException, Header, Depends
from database.database import database
from datetime import datetime, timedelta
import pytz
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
    """
    アバター以外のユーザー情報を更新するAPI
    """
    async def send_message_to_ws(ws, id, name, avatar_path, is_frinend):
        """
        非同期的に更新されたユーザー情報を送信
        """
        print("send_message_to_ws")
        await manager.send_personal_message({
            "type":"UpdateUser",
            "content":{
                "id":id,
                "name":name,
                "avatar_path":f"/avatars/users{avatar_path}",
                "is_friend":is_frinend}},
            ws)

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
                
                #ユーザー情報をフレンド及びルーム参加者に通知
                users_id = []
                rooms_id = []
                friends = database.fetch(cursor, "friendships", {"id":userid})
                for friend in friends:
                    if not str(friend["friend_id"]) in [id[0] for id in users_id]:
                        users_id.append((str(friend["friend_id"]),True))
                rooms = database.fetch(cursor, "room_participants", {"user_id":userid})
                for room in rooms:
                    if not str(room["id"]) in rooms_id:
                        rooms_id.append(str(room["id"]))
                room_participants = database.in_fetch(cursor, "room_participants", "id", rooms_id)
                for room_participant in room_participants:
                    if not str(room_participant["user_id"]) in [id[0] for id in users_id] and not str(room_participant["user_id"]) == userid:
                        users_id.append((str(room_participant["user_id"]),False))
                for participant in users_id:
                    if participant[0] in manager.active_connections:
                        friend_ws = manager.active_connections[participant[0]]
                        asyncio.run(send_message_to_ws(friend_ws, userid, body.name, user[0]["avatar_path"], participant[1]))
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