from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database.database import database
from hashed import hashed
from datetime import datetime, timedelta
import pytz

router = APIRouter()

@router.delete("/users/{user_name}", status_code=204)
async def users_delete(request:Request,user_name:str):
    user = []
    token = []
    try:
        user = database.fetch("users", {"name": user_name})
        token = database.fetch("access_tokens", {"access_token": request.headers['access-token']})
    except Exception as e:
        print(f"Error fetching user data: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user data")
    
    if user == []:
        raise HTTPException(status_code=401, detail="User not found")
        
    #パスワードの確認及びアクセストークンの有効期限の確認及びデバイスIDの確認(同一デバイスであるか)
    if (not user[0]["access_token"] == request.headers['access-token'] or 
        not datetime.now(pytz.timezone('Asia/Tokyo')) < token[0]["created_at"]+timedelta(hours=token[0]["validity_hours"]) or 
        not hashed.verify_pw(request.headers['password'], user[0]["hash_password"], user[0]["salt"]) or
        not user[0]["device_id"] == request.headers['device_id']
        ):
        raise HTTPException(status_code=401, detail="Invalid auth")
    
    #ユーザー情報の削除
    try:
        if (database.delete("users", {"name":user_name}) and
            database.delete("access_tokens", {"access_token":user[0]["access_token"]}) and
            database.delete("refresh_tokens", {"refresh_token":user[0]["refresh_token"]})
            ):
            return
        else:
            raise Exception
    except Exception as e:
        print(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail="Error deleting user")