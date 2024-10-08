from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from database.database import database
from hashed import hashed
import secrets
import string
from datetime import datetime, timedelta
import pytz
from config import VALIDITY_HOURS
from psycopg.rows import dict_row

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str
    deviceid: str
    fcmtoken: str

def generate_tokens(user: LoginRequest, userdata, new_tokens):
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("BEGIN")
                if database.update(
                    cursor,
                    "users",
                    {"device_id":user.deviceid,"access_token":new_tokens["access_token"],"refresh_token":new_tokens["refresh_token"],"fcm_token":user.fcmtoken},
                    {"email":user.email}
                ) and database.update(
                    cursor,
                    "access_tokens",
                    {"access_token":new_tokens["access_token"], "validity_hours":VALIDITY_HOURS["access_token"], "created_at":datetime.now(pytz.timezone('Asia/Tokyo'))},
                    {"access_token":userdata[0]["access_token"]}
                ) and database.update(
                    cursor,
                    "refresh_tokens",
                    {"refresh_token":new_tokens["refresh_token"], "validity_hours":VALIDITY_HOURS["refresh_token"], "created_at":datetime.now(pytz.timezone('Asia/Tokyo'))},
                    {"refresh_token":userdata[0]["refresh_token"]}
                ):
                    conn.commit()
                    return True
                else:
                    raise Exception
    except Exception as e:
        print(f"Error update tokens: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        return False

@router.post("/auth/login", status_code=200)
def users_login(user:LoginRequest):
    userdata = []
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                userdata = database.fetch(cursor,"users", {"email": user.email})
    except Exception as e:
        print(f"Error fetching user data: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user data")
    
    if userdata == []:#ユーザーが存在しない場合
        raise HTTPException(status_code=401, detail="User not found")
    if hashed.verify_pw(user.password, userdata[0]["hash_password"], userdata[0]["salt"]):#ユーザーが存在する場合
        try:
            new_tokens = {
                "access_token": ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(32)),
                "refresh_token": ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(64))
            }
            if generate_tokens(user, userdata, new_tokens):
                token_created = pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)
                return {
                    "detail": "Login successful",
                    "user_name": userdata[0]["name"],
                    "user_id": userdata[0]["id"],
                    "avatar_path": f"/avatars/users{userdata[0]['avatar_path']}",
                    "access_token": new_tokens["access_token"],
                    "access_token_expires": (token_created+timedelta(hours=VALIDITY_HOURS["access_token"])).isoformat(' '),
                    "refresh_token": new_tokens["refresh_token"],
                    "refresh_token_expires": (token_created+timedelta(hours=VALIDITY_HOURS["refresh_token"])).isoformat(' ')
                }
            else:
                raise Exception
        except Exception as e:
            print(f"Error generating tokens: {e}")
            raise HTTPException(status_code=500, detail="Error generating tokens")
    else:#パスワードが間違っている場合
        raise HTTPException(status_code=403, detail="Invalid password")
