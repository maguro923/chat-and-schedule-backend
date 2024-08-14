from fastapi import APIRouter, HTTPException
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

import string
import secrets
from hashed import hashed

router = APIRouter()

def password_validator(password:str,info: ValidationInfo) -> str:
    IsError = False
    error_message = []
    if len(password) < 8:
        IsError = True
        error_message.append("Password must be at least 8 characters")
    if len(password) > 32:
        IsError = True
        error_message.append("Password must be at most 32 characters")
    if not re.search(r"[A-Z]",password):
        IsError = True
        error_message.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]",password):
        IsError = True
        error_message.append("Password must contain at least one lowercase letter")
    if not re.search(r"[0-9]",password):
        IsError = True
        error_message.append("Password must contain at least one number")
    if IsError:
        raise ValueError(error_message)
    else:
        return password

class RegisterRequest(BaseModel):
    username: Annotated[str,Field(min_length=4, max_length=32, pattern=r"^[A-Za-z0-9ぁ-んァ-ン_?!+-@]+$")]
    email: EmailStr
    password: Annotated[str,AfterValidator(password_validator)]
    deviceid: str
    fcmtoken: str

def register_user(body:RegisterRequest, password:dict, tokens:dict, id:string) -> bool:
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("BEGIN")
                if (database.insert(
                    cursor,
                    "users",
                    {
                        "id":id,
                        "name":body.username,
                        "email":body.email,
                        "hash_password":password["hash"],
                        "salt": password["salt"],
                        "device_id":body.deviceid,
                        "fcm_token":body.fcmtoken,
                        "access_token":tokens["access_token"],
                        "refresh_token":tokens["refresh_token"]
                    }
                ) and database.insert(
                    cursor,
                    "access_tokens",
                    {
                        "access_token":tokens["access_token"],
                        "validity_hours":VALIDITY_HOURS["access_token"]
                    }
                ) and database.insert(
                    cursor,
                    "refresh_tokens",
                    {
                        "refresh_token":tokens["refresh_token"],
                        "validity_hours":VALIDITY_HOURS["refresh_token"]
                    }
                )):
                    conn.commit()
                    return True
                else:
                    raise Exception
    except Exception as e:
        print(f"Error registering user: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        return False

@router.post("/users", status_code=201)
def users_register(body:RegisterRequest):
    with database.get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            if not database.fetch(cursor,"users", {"email":body.email}) == []:
                raise HTTPException(status_code=409, detail="Email already registered")

    password = { "salt":secrets.token_hex(128) }
    password["hash"] = hashed.generate_hash(body.password, password["salt"])
    tokens = {
        "access_token": ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(32)),
        "refresh_token": ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(64))
    }
    id = str(uuid4())
    if not password["hash"] == None and register_user(body, password, tokens, id):
        token_created = pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)
        return {
            "detail": "User registered",
            "user_id": id,
            "access_token": tokens["access_token"],
            "access_token_expires": (token_created+timedelta(hours=VALIDITY_HOURS["access_token"])).isoformat(' '),
            "refresh_token": tokens["refresh_token"],
            "refresh_token_expires": (token_created+timedelta(hours=VALIDITY_HOURS["refresh_token"])).isoformat(' ')
        }
    else:
        raise HTTPException(status_code=500, detail="Error registering user")
