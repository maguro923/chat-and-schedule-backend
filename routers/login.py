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

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str
    deviceid: str

def generate_tokens(user: LoginRequest, userdata, new_tokens):
    try:
        #print(new_tokens["access_token"])
        return database.update(
            "users",
            {"device_id":user.deviceid,"access_token":new_tokens["access_token"],"refresh_token":new_tokens["refresh_token"]},
            {"name":user.username}
        ) and database.update(
            "access_tokens",
            {"access_token":new_tokens["access_token"], "validity_hours":VALIDITY_HOURS["access_token"], "created_at":datetime.now(pytz.timezone('Asia/Tokyo'))},
            {"access_token":userdata[0]["access_token"]}
        ) and database.update(
            "refresh_tokens",
            {"refresh_token":new_tokens["refresh_token"], "validity_hours":VALIDITY_HOURS["refresh_token"], "created_at":datetime.now(pytz.timezone('Asia/Tokyo'))},
            {"refresh_token":userdata[0]["refresh_token"]}
        )
    except Exception as e:
        print(f"Error update tokens: {e}")
        return False

@router.post("/auth/login", status_code=200)
def users_login(user:LoginRequest):
    userdata = []
    try:
        userdata = database.fetch("users", {"name": user.username})
    except Exception as e:
        print(f"Error fetching user data: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user data")
    #print(userdata[0])
    if userdata == []:#ユーザーが存在しない場合
        raise HTTPException(status_code=401, detail="User not found")
    if hashed.verify_pw(user.password, userdata[0]["hash_password"], userdata[0]["salt"]):#ユーザーが存在する場合
        try:
            new_tokens = {
                "access_token": ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(32)),
                "refresh_token": ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(64))
            }
            if generate_tokens(user, userdata, new_tokens):
                #a=database.fetch("access_tokens", {"access_token":new_tokens["access_token"]})
                print(new_tokens["access_token"])
                #print(a)
                token_created = datetime.now(pytz.timezone('Asia/Tokyo'))
                return {
                    "detail": "Login successful",
                    "access_token": new_tokens["access_token"],
                    "access_token_expires": (token_created+timedelta(hours=VALIDITY_HOURS["access_token"])).isoformat(),
                    "refresh_token": new_tokens["refresh_token"],
                    "refresh_token_expires": (token_created+timedelta(hours=VALIDITY_HOURS["refresh_token"])).isoformat()
                }
            else:
                raise Exception
        except Exception as e:
            print(f"Error generating tokens: {e}")
            raise HTTPException(status_code=500, detail="Error generating tokens")
    else:#パスワードが間違っている場合
        raise HTTPException(status_code=403, detail="Invalid password")
