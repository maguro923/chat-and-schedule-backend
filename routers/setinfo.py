from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, Header, Depends
from database.database import database
import os
from datetime import datetime, timedelta
import pytz
import glob
from psycopg.rows import dict_row

router = APIRouter()

def get_user_headers(
    device_id: str = Header(...),
    access_token: str = Header(...),
    username: str = Header(...)
):
    if not device_id or not access_token or not username:
        raise HTTPException(status_code=400, detail="Invalid headers")
    return {"device_id": device_id, "access_token": access_token, "username": username}

@router.post("/users/{userid}", status_code=201)
def set_userinfo(userid:str, headers:dict = Depends(get_user_headers)):
    #アップロードされたファイルの保存
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
                if not database.update(cursor, "users", {"name":headers["username"], "updated_at":pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)}, {"id":userid}):
                    raise Exception
                conn.commit()
                return {"detail": "infomation updated"}
    except Exception as e:
        print(f"Error saving infomation: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        raise HTTPException(status_code=500, detail="Error saving infomation")
