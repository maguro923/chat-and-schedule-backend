from fastapi import APIRouter, HTTPException, Request, Depends, Header
from pydantic import BaseModel
from database.database import database
from hashed import hashed
from datetime import datetime, timedelta
import pytz
from psycopg.rows import dict_row

router = APIRouter()

def delete_user(user_name:str, user:dict) -> bool:
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("BEGIN")
                if (database.delete(cursor,"users", {"name":user_name}) and
                    database.delete(cursor,"access_tokens", {"access_token":user[0]['access_token']}) and
                    database.delete(cursor,"refresh_tokens", {"refresh_token":user[0]['refresh_token']})
                ):
                    conn.commit()
                    return True
                else:
                    raise Exception
    except Exception as e:
        print(f"Error deleting user: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        return False

def get_headers(
    password: str = Header(...),
    device_id: str = Header(...),
    access_token: str = Header(...)
):
    if not password or not device_id or not access_token:
        raise HTTPException(status_code=400, detail="Invalid headers")
    return {"password": password, "device_id": device_id, "access_token": access_token}

@router.delete("/users/{user_name}", status_code=204)
def users_delete(request:Request,user_name:str, headers:dict = Depends(get_headers)):
    user = []
    token = []
    print(headers)
    print(request.headers)
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                user = database.fetch(cursor,"users", {"name": user_name})
                token = database.fetch(cursor,"access_tokens", {"access_token": headers['access_token']})
    except Exception as e:
        print(f"Error fetching user data: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user data")
    
    if user == []:
        raise HTTPException(status_code=401, detail="User not found")
        
    #パスワードの確認及びアクセストークンの有効期限の確認及びデバイスIDの確認(同一デバイスであるか)
    if (not user[0]["access_token"] == headers['access_token'] or 
        not datetime.now(pytz.timezone('Asia/Tokyo')) < token[0]["created_at"]+timedelta(hours=token[0]["validity_hours"]) or 
        not hashed.verify_pw(headers['password'], user[0]["hash_password"], user[0]["salt"]) or
        not user[0]["device_id"] == headers['device_id']
        ):
        raise HTTPException(status_code=401, detail="Invalid auth")
    
    #ユーザー情報の削除
    try:
        if delete_user(user_name, user):
            return
        else:
            raise Exception
    except Exception as e:
        print(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail="Error deleting user")