from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, File
from database.database import database
import os

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

@router.post("/avatars/{type}/{userid}", status_code=201)
def post_avatar(file: UploadFile, type:str, userid:str):
    #アップロードされたファイルの保存
    try:
        with database.get_connection() as conn:
            with conn.cursor() as cursor:
                user = database.fetch(cursor, "users", {"id":userid})
                if user == []:
                    raise HTTPException(status_code=404, detail="User not found")
                print(file.filename)
                os.makedirs(f"./avatars/{type}/{userid}", exist_ok=True)
                with open (f"./avatars/{type}/{userid}/{file.filename}", "wb") as f:
                    f.write(file.file.read())
                cursor.execute("BEGIN")
                path = f"{type}/{userid}/{file.filename}"
                if not database.update(cursor, "users", {"avatar_path":file.filename}, {"id":userid}):
                    raise Exception
                conn.commit()
    except Exception as e:
        print(f"Error saving avatar: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        raise HTTPException(status_code=500, detail="Error saving avatar")
    return {"detail": "avatar uploaded"}
