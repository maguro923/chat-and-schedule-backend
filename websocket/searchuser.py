from fastapi import WebSocket, Response
from datetime import datetime, timedelta
import pytz
import uuid
from database.database import database
from psycopg.rows import dict_row
from websocket.manager import manager

async def SearchUsers(ws: WebSocket, user_id: str, data: dict):
    """
    ユーザー検索リクエストを処理する
    """
    def msg_key_check(data: dict):
        content = data["content"]
        if not "key" in content.keys():
            raise KeyError

    try:
        msg_key_check(data)
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-SearchUsers","content":{"message":"Invalid message format"}}, ws)
        return

    users = []
    search_key = data["content"]["key"]
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                if (search_key == None or search_key == ""):
                    await manager.send_personal_message({"id":data["id"],"type":"reply-SearchUsers","content":{"message":"Invalid search key"}}, ws)
                    return
                elif search_key in '#':
                    # ID検索
                    users = database.fetch(cursor, "users", {"id":search_key})
                else:
                    #名前検索 個数制限あり
                    users = database.like(cursor, "users", {}, {"name":search_key},"21")
                    is_same = False
                    for i in range(len(users)):
                        if str(users[i]["id"]) == user_id:
                            users.pop(i)
                            is_same = True
                            break
                    if not is_same:
                        users.pop(len(users)-1)
                await manager.send_personal_message({"id":data["id"],"type":"reply-SearchUsers","content":users}, ws)
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-SearchUsers","content":{"message":"Error fetching user data"}}, ws)
        print(f"Error fetching user data: {e}")
        