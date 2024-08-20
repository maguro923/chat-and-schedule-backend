from fastapi import APIRouter, HTTPException, Request, Header, Depends
from pydantic import BaseModel, Field, EmailStr, AfterValidator, ValidationInfo
from typing import List
from database.database import database
import asyncio
from datetime import datetime, timedelta
import pytz
from typing_extensions import Annotated
from config import VALIDITY_HOURS
import re
from uuid import uuid4
from psycopg.rows import dict_row
import psycopg

router = APIRouter()

def get_headers(
    access_token: str = Header(...),
    user_id: str = Header(...),
    participants_id: List[str] = Header(...)
):
    if not access_token or not user_id or not participants_id:
        raise HTTPException(status_code=422, detail="Invalid headers")
    return {"access_token": access_token, "user_id": user_id, "participants_id": participants_id}

@router.get("/users", status_code=200)
def userdinfo(request:Request, headers:dict = Depends(get_headers)):
    user = []
    token = []
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                user = database.fetch(cursor,"users", {"id": headers['user_id']})
                token = database.fetch(cursor,"access_tokens", {"access_token": headers['access_token']})
    except psycopg.errors.InvalidTextRepresentation as e:
        print(f"Error fetching user data: {e}")
        raise HTTPException(status_code=400, detail="Invalid user_id type")
    except Exception as e:
        print(f"Error fetching user data: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user data")
    
    if user == [] or token == []:
        raise HTTPException(status_code=401, detail="User not found")

    print(pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9))

    #アクセストークンの確認及び有効期限の確認
    if (not user[0]["access_token"] == headers['access_token'] or 
        not pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9) < token[0]["created_at"]+timedelta(hours=token[0]["validity_hours"])):
        raise HTTPException(status_code=401, detail="Invalid auth")
    
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                response = {}
                for participant_id in headers['participants_id']:
                    user_info = {}
                    #ユーザ情報の取得
                    user = database.fetch(cursor,"users", {"id": participant_id})
                    if user == []:
                        raise HTTPException(status_code=404, detail="Participant not found")
                    user_info["name"] = str(user[0]["name"])
                    avatar_path = f"/avatars/users/{user[0]["avatar_path"]}"
                    user_info["avatar_path"] = avatar_path
                    #ユーザが友達かどうかの確認
                    is_friend = database.fetch(cursor,"friendships", {"id": headers['user_id'], "friend_id": participant_id})
                    if is_friend == []:
                        user_info["is_friend"] = False
                    else:
                        user_info["is_friend"] = True
                    response[participant_id]=user_info

                return {
                    "detail": "success",
                    "users_info": response
                }
    except Exception as e:
        print(f"Error fetching user data: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user data")