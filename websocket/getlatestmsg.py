from fastapi import WebSocket
from typing import Dict
from datetime import datetime, timedelta
import pytz
from database.database import database
from psycopg.rows import dict_row
from websocket.manager import manager

async def get_latest_message(ws: WebSocket, user_id: str):
    """
    最新のメッセージ(未読のメッセージ)を取得し送信する
    """
    # ユーザーが参加しているルームの最新のメッセージを送信
    message = []
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                join_rooms = database.fetch(cursor, "room_participants", {"user_id": user_id})
                if join_rooms == []:
                    return
                room_ids = [str(room["id"]) for room in join_rooms]
                rooms_last_viewed_at = {str(room["id"]): room["last_viewed_at"] for room in join_rooms}
                for room_id in room_ids:
                    latest_message = database.fetch_after_datetime(cursor, "messages", {"room_id":room_id},"created_at", str(rooms_last_viewed_at[room_id]))
                    if latest_message == []:
                        continue
                    for i in range(len(latest_message)):
                        latest_message[i]["id"] = str(latest_message[i]["id"])
                        latest_message[i]["room_id"] = str(latest_message[i]["room_id"])
                        latest_message[i]["sender_id"] = str(latest_message[i]["sender_id"])
                        latest_message[i]["created_at"] = str(latest_message[i]["created_at"])
                    message += latest_message
                if message == []:
                    #await manager.send_personal_message({"type":"Latest-Message","content":{"message":"No new messages"}}, ws)
                    return
                await manager.send_personal_message({"type":"Latest-Message","content":message}, ws)
    except Exception as e:
        print(f"Error fetching message data: {e}")
        await manager.send_personal_message({"type":"Latest-Message","content":{"message":"Error fetching message data"}}, ws)
        return
    
    #ユーザに対するフレンドリクエストが来ている場合は送信
    try:
        friend_requests = []
        if user_id in manager.friend_requests and not manager.friend_requests[user_id] == []:
            friend_requests = manager.friend_requests[user_id]
            await manager.send_personal_message({"type":"Latest-FriendRequest","content":friend_requests}, ws)
    except Exception as e:
        print(f"Error fetching friend request data: {e}")
        await manager.send_personal_message({"type":"Latest-FriendRequest","content":{"message":"Error fetching friend request data"}}, ws)
        return