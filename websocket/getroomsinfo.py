from fastapi import WebSocket
from typing import Dict
from database.database import database
from psycopg.rows import dict_row
from websocket.manager import manager

async def GetRoomsInfo(ws: WebSocket, user_id: str, data: Dict):
    """
    ルーム情報取得リクエストを処理する
    """
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                rooms = database.fetch(cursor, "room_participants", {"user_id": user_id})
                if rooms == []:
                    await manager.send_personal_message({"id":data["id"],"type":"reply-GetRoomsInfo","content":{"roomlist":[],"participants":{}}}, ws)
                    return
                rooms_info = []
                participants = {}
                for room in rooms:
                    room_info = {}
                    room_data = database.fetch(cursor, "rooms", {"id": str(room["id"])})
                    room_info["name"] = room_data[0]["name"]
                    room_info["avatar_path"] = f"avatars/rooms{room_data[0]["avatar_path"]}"
                    room_info["id"] = str(room["id"])
                    room_info["joined_at"] = str(room["joined_at"])
                    rooms_info.append(room_info)
                    room_participants = database.fetch(cursor, "room_participants", {"id": str(room["id"])})
                    participants[str(room["id"])] = []
                    for participant in room_participants:
                        participants[str(room["id"])].append(str(participant["user_id"]))
                message = {"id":data["id"],"type":"reply-GetRoomsInfo","content":{"roomlist":rooms_info,"participants":participants}}
                await manager.send_personal_message(message, ws)
    except Exception as e:
        print(f"Error fetching room data: {e}")
        await manager.send_personal_message({"id":data["id"],"type":"reply-GetRoomsInfo","content":{"message":"Error fetching room data"}}, ws)
        return