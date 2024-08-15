from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Response
from typing import Dict
import asyncio
import json
from config import VALIDITY_HOURS
from datetime import datetime, timedelta
import pytz
import uuid
from database.database import database
from psycopg.rows import dict_row

async def check_user_id(ws: WebSocket, user_id: str) -> bool:
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
        response = Response(status_code=400, content="Invalid user_id format")
        await ws.send_denial_response(response)
        return False, None
    
    access_token = ""
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                user = database.fetch(cursor,"users", {"id": user_id})
                if user == []:
                    response = Response(status_code=404, content="User not found")
                    await ws.send_denial_response(response)
                    return False, None
                access_token = user[0]["access_token"]
    except Exception as e:
        print(f"Error fetching user data: {e}")
        response = Response(status_code=500, content="Internal Server Error")
        await ws.send_denial_response(response)
        return False, None
    if access_token == None or access_token == "":
        response = Response(status_code=500, content="Internal Server Error")
        await ws.send_denial_response(response)
        return False, None
    
    return True, access_token

async def check_access_token(ws: WebSocket, user_id: str, users_access_token) -> bool:
    """
    アクセストークンの確認
    """
    access_token = ws.headers.get("access-token")
    if access_token == None:
        response = Response(status_code=401, content="invalid headers")
        await ws.send_denial_response(response)
        return False
    if access_token != users_access_token:
        response = Response(status_code=401, content="invalid access_token")
        await ws.send_denial_response(response)
        return False
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                access_token_data = database.fetch(cursor,"access_tokens", {"access_token": access_token})
                if access_token_data == []:
                    response = Response(status_code=401, content="invalid access_token")
                    await ws.send_denial_response(response)
                    return False
                if not pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9) < access_token_data[0]["created_at"]+timedelta(hours=access_token_data[0]["validity_hours"]):
                    response = Response(status_code=403, content="access_token expired")
                    await ws.send_denial_response(response)
                    return False
    except Exception as e:
        print(f"Error checking access_token: {e}")
        response = Response(status_code=500, content="Internal Server Error")
        await ws.send_denial_response(response)
        return False
    return True
