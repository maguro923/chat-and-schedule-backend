from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, Header, Depends
from database.database import database
import os
from datetime import datetime, timedelta
import pytz
import glob
from psycopg.rows import dict_row

router = APIRouter()

@router.get("/avatars/{raw_file_path:path}", status_code=200)
def get_avatar(request:Request, raw_file_path:str):
    file_path = raw_file_path.split("/")
    #パスの形式が正しいか確認
    if ((len(file_path) != 2 and len(file_path) != 3) or
        (len(file_path) == 2 and file_path[1] != "default.png" and (file_path[0] != "users" and file_path[0] != "rooms")) or
        (len(file_path) == 3 and (file_path[0] != "users" and file_path[0] != "rooms"))):
        raise HTTPException(status_code=404, detail="Invalid path")
    #デフォルトアバターの取得
    elif len(file_path) == 2:
        type = file_path[0]
        with open (f"./avatars/{type}/default.png", "rb") as f:
            return Response(content=f.read(), media_type="image/png")
    #ユーザまたはルームの独自アバターの取得
    elif len(file_path) == 3:
        type = file_path[0]
        id = file_path[1]
        file_name = file_path[2]
        image_type = file_name.split('.')[-1]
        try:
            with open (f"./avatars/{type}/{id}/{file_name}", "rb") as f:
                return Response(content=f.read(), media_type=f"image/{image_type}")
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail="File not found")
        except Exception as e:
            print(f"Error getting avatar: {e}")
            raise HTTPException(status_code=500, detail="Error getting avatar")

def get_user_headers(
    device_id: str = Header(...),
    access_token: str = Header(...)
):
    if not device_id or not access_token:
        raise HTTPException(status_code=400, detail="Invalid headers")
    return {"device_id": device_id, "access_token": access_token}

@router.post("/avatars/users/{userid}", status_code=201)
def post_useravatar(file: UploadFile, userid:str, headers:dict = Depends(get_user_headers)):
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
                
                os.makedirs(f"./avatars/users/{userid}", exist_ok=True)
                #既存のアバター画像を削除
                for p in glob.glob(f"./avatars/users/{userid}/avatar-*.png", recursive=True):
                    if os.path.isfile(p):
                        os.remove(p)
                #アバター画像の保存
                with open (f"./avatars/users/{userid}/{file.filename}", "wb") as f:
                    f.write(file.file.read())
                cursor.execute("BEGIN")
                path = f"/{userid}/{file.filename}"
                if not database.update(cursor, "users", {"avatar_path":path, "updated_at":pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)}, {"id":userid}):
                    raise Exception
                conn.commit()
                return {"detail": "avatar uploaded"}
    except Exception as e:
        print(f"Error saving avatar: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        raise HTTPException(status_code=500, detail="Error saving avatar")

def get_room_headers(
    device_id: str = Header(...),
    access_token: str = Header(...),
    user_id: str = Header(...)
):
    if not device_id or not access_token or not user_id:
        raise HTTPException(status_code=400, detail="Invalid headers")
    return {"device_id": device_id, "access_token": access_token, "user_id": user_id}

@router.post("/avatars/rooms/{roomid}", status_code=201)
def post_roomavatar(file: UploadFile, roomid:str, headers:dict = Depends(get_room_headers)):
    #アップロードされたファイルの保存
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                user = database.fetch(cursor, "users", {"id":headers["user_id"]})
                token = database.fetch(cursor,"access_tokens", {"access_token": headers['access_token']})
                if user == []:
                    raise HTTPException(status_code=404, detail="User not found")
                
                #パスワードの確認及びアクセストークンの有効期限の確認及びデバイスIDの確認(同一デバイスであるか)
                if (not user[0]["access_token"] == headers['access_token'] or 
                    not pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9) < token[0]["created_at"]+timedelta(hours=token[0]["validity_hours"]) or 
                    not user[0]["device_id"] == headers['device_id']):
                    raise HTTPException(status_code=401, detail="Invalid auth")
                
                os.makedirs(f"./avatars/rooms/{roomid}", exist_ok=True)
                #既存のアバター画像を削除
                for p in glob.glob(f"./avatars/rooms/{roomid}/avatar-*.png", recursive=True):
                    if os.path.isfile(p):
                        os.remove(p)
                #アバター画像の保存
                with open (f"./avatars/rooms/{roomid}/{file.filename}", "wb") as f:
                    f.write(file.file.read())
                cursor.execute("BEGIN")
                path = f"/{roomid}/{file.filename}"
                if not database.update(cursor, "rooms", {"avatar_path":path, "updated_at":pytz.timezone('Asia/Tokyo').localize(datetime.now())+timedelta(hours=9)}, {"id":roomid}):
                    raise Exception
                conn.commit()
                return {"detail": "avatar uploaded"}
    except Exception as e:
        print(f"Error saving avatar: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        raise HTTPException(status_code=500, detail="Error saving avatar")