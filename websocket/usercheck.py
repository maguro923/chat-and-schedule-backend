from fastapi import WebSocket, Response
from datetime import datetime, timedelta
import pytz
import uuid
from database.database import database
from psycopg.rows import dict_row
from websocket.manager import manager

async def check_user_id(ws:WebSocket, user_id: str) -> bool:
    """
    ユーザーIDの確認
    """
    def is_valid_uuid(value):
        try:
            uuid.UUID(value, version=4)
            return True
        except ValueError:
            return False
        except Exception as e:
            print(f"Error checking uuid: {e}")
            return False
    
    if user_id == None or is_valid_uuid(user_id) == False:
        response = {"type":"reply-init","content":{"status":"400", "message":"Invalid user_id format"}}
        await manager.send_personal_message(response,ws)
        return False, None
    
    access_token = ""
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                user = database.fetch(cursor,"users", {"id": user_id})
                if user == []:
                    response = {"type":"reply-init", "content":{"stauts":"404","message":"User not found"}}
                    await manager.send_personal_message(response,ws)
                    return False, None
                access_token = user[0]["access_token"]
    except Exception as e:
        print(f"Error fetching user data: {e}")
        response = {"type":"reply-init", "content":{"stauts":"500","message":"Internal Server Error"}}
        await manager.send_personal_message(response,ws)
        return False, None
    if access_token == None or access_token == "":
        response = {"type":"reply-init", "content":{"stauts":"500","message":"Internal Server Error"}}
        await manager.send_personal_message(response,ws)
        return False, None
    
    return True, access_token

async def check_access_token(ws: WebSocket, data, users_access_token) -> bool:
    """
    アクセストークンの確認
    """
    access_token = data["content"]["access_token"]
    if access_token != users_access_token:
        response = {"type":"reply-init", "content":{"stauts":"401","message":"invalid access_token"}}
        await manager.send_personal_message(response,ws)
        return False
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                access_token_data = database.fetch(cursor,"access_tokens", {"access_token": access_token})
                if access_token_data == []:
                    response = {"type":"reply-init", "content":{"stauts":"401","message":"invalid access_token"}}
                    await manager.send_personal_message(response,ws)
                    return False
                if not pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9) < access_token_data[0]["created_at"]+timedelta(hours=access_token_data[0]["validity_hours"]):
                    response = {"type":"reply-init", "content":{"stauts":"403","message":"access_token expired"}}
                    await manager.send_personal_message(response,ws)
                    return False
    except Exception as e:
        print(f"Error checking access_token: {e}")
        response = {"type":"reply-init", "content":{"stauts":"500","message":"Internal Server Error"}}
        await manager.send_personal_message(response,ws)
        return False
    return True
