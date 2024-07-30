from fastapi import APIRouter, HTTPException, Request
from database.database import database
from datetime import datetime, timedelta
import pytz
import string
import secrets
from config import VALIDITY_HOURS

router = APIRouter()

@router.post("/auth/refresh", status_code=200)
async def users_refresh(request:Request):#header: refresh_token device_id
    user = []
    refresh_token = []
    try:
        user = database.fetch("users", {"refresh_token": request.headers['refresh_token']})
        refresh_token = database.fetch("refresh_tokens", {"refresh_token": request.headers['refresh_token']})
    except Exception as e:
        print(f"Error fetching user data: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user data")
    
    #リフレッシュトークンの確認
    if refresh_token == [] or user == []:
        raise HTTPException(status_code=401, detail="refresh_token not found")
    
    #リフレッシュトークンの有効期限の確認
    if not datetime.now(pytz.timezone('Asia/Tokyo')) < refresh_token[0]["created_at"]+timedelta(hours=refresh_token[0]["validity_hours"]):
        raise HTTPException(status_code=403, detail="refresh_token expired")
    
    #デバイスIDの確認(同一デバイスであるか)
    if not user[0]["device_id"] == request.headers['device_id']:
        raise HTTPException(status_code=403, detail="Invalid device_id")
    
    #新しいトークンの生成
    try:
        new_access_token = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(32))
        if (database.delete("access_tokens", {"access_token":user[0]["access_token"]}) and
            database.update("users", {"access_token":new_access_token}, {"refresh_token":request.headers['refresh_token']}) and
            database.insert("access_tokens", {"access_token":new_access_token, "validity_hours":VALIDITY_HOURS["access_token"]})
            ):
            token_created = datetime.now(pytz.timezone('Asia/Tokyo'))
            return {
                "detail": "access_token regenerated",
                "access_token": new_access_token,
                "access_token_expires": (token_created+timedelta(hours=VALIDITY_HOURS["access_token"])).isoformat(),
            }
        else:
            raise Exception
    except Exception as e:
        print(f"Error refreshing tokens: {e}")
        raise HTTPException(status_code=500, detail="Error refreshing tokens")