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


def register_user(body:RegisterRequest, password:dict, tokens:dict) -> bool:
    return database.insert(
        "users",
        {
            "name":body.username,
            "email":body.email,
            "hash_password":password["hash"],
            "salt": password["salt"],
            "device_id":body.deviceid,
            "access_token":tokens["access_token"],
            "refresh_token":tokens["refresh_token"]
        }
    ) and database.insert(
        "access_tokens",
        {
            "access_token":tokens["access_token"],
            "validity_hours":VALIDITY_HOURS["access_token"]
        }
    ) and database.insert(
        "refresh_tokens",
        {
            "refresh_token":tokens["refresh_token"],
            "validity_hours":VALIDITY_HOURS["refresh_token"]
        }
    )

@router.post("/users", status_code=201)
async def users_register(body:RegisterRequest):
    if not database.fetch("users", {"name":body.username}) == []:
        raise HTTPException(status_code=409, detail="User already exists")
    elif not database.fetch("users", {"email":body.email}) == []:
        raise HTTPException(status_code=409, detail="Email already registered")
    else:
        password = { "salt":secrets.token_hex(128) }
        password["hash"] = hashed.generate_hash(body.password, password["salt"])
        tokens = {
            "access_token": ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(32)),
            "refresh_token": ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(64))
        }
        if not hash == None and register_user(body, password, tokens):
            token_created = datetime.now(pytz.timezone('Asia/Tokyo'))
            return {
                "detail": "User registered",
                "access_token": tokens["access_token"],
                "access_token_expires": (token_created+timedelta(hours=VALIDITY_HOURS["access_token"])).isoformat(),
                "refresh_token": tokens["refresh_token"],
                "refresh_token_expires": (token_created+timedelta(hours=VALIDITY_HOURS["refresh_token"])).isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Error registering user")
