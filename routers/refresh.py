from fastapi import APIRouter, HTTPException, Request, Header, Depends
from database.database import database
from datetime import datetime, timedelta
import pytz
import string
import secrets
from config import VALIDITY_HOURS
from psycopg.rows import dict_row

router = APIRouter()

def generate_tokens(user: dict, new_access_token: dict, headers: dict):
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("BEGIN")
                if (database.delete(cursor,"access_tokens", {"access_token":user[0]["access_token"]}) and
                    database.update(cursor,"users", {"access_token":new_access_token}, {"refresh_token":headers['refresh_token']}) and
                    database.insert(cursor,"access_tokens", {"access_token":new_access_token, "validity_hours":VALIDITY_HOURS["access_token"]})
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

def get_headers(
    refresh_token: str = Header(...),
    device_id: str = Header(...)
):
    if not refresh_token or not device_id:
        raise HTTPException(status_code=422, detail="Invalid headers")
    return {"refresh_token": refresh_token, "device_id": device_id}

@router.post("/auth/refresh", status_code=200)
def users_refresh(request:Request, headers:dict = Depends(get_headers)):#header: refresh_token device_id
    user = []
    refresh_token = []
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                user = database.fetch(cursor,"users", {"refresh_token": headers['refresh_token']})
                refresh_token = database.fetch(cursor,"refresh_tokens", {"refresh_token": headers['refresh_token']})
    except Exception as e:
        print(f"Error fetching user data: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user data")
    
    #リフレッシュトークンの確認
    if refresh_token == [] or user == []:
        raise HTTPException(status_code=401, detail="refresh_token not found")
    
    #リフレッシュトークンの有効期限の確認
    if not pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9) < refresh_token[0]["created_at"]+timedelta(hours=refresh_token[0]["validity_hours"]):
        raise HTTPException(status_code=403, detail="refresh_token expired")
    
    #デバイスIDの確認(同一デバイスであるか)
    if not user[0]["device_id"] == headers['device_id']:
        raise HTTPException(status_code=403, detail="Invalid device_id")
    
    #新しいトークンの生成
    try:
        new_access_token = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(32))
        if generate_tokens(user, new_access_token, headers):
            token_created = pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)
            print(token_created)
            return {
                "detail": "access_token regenerated",
                "access_token": new_access_token,
                "access_token_expires": (token_created+timedelta(hours=VALIDITY_HOURS["access_token"])).isoformat(' '),
            }
        else:
            raise Exception
    except Exception as e:
        print(f"Error refreshing tokens: {e}")
        raise HTTPException(status_code=500, detail="Error refreshing tokens")