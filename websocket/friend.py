from fastapi import WebSocket
from typing import Dict
from datetime import datetime, timedelta
import pytz
from database.database import database
from psycopg.rows import dict_row
from websocket.manager import manager

async def Friend(ws: WebSocket, user_id: str, data: Dict):
    """
    友達申請リクエストを処理する
    """
    def msg_key_check(data: Dict):
        content = data["content"]
        if (not "friend_id" in content.keys()):
            raise KeyError
    
    async def is_friend(user_id: str, friend_id: str) -> bool:
        """
        既に友達か確認する
        """
        try:
            with database.get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    is_friend = database.fetch(cursor,"friendships", {"id": user_id, "friend_id": friend_id})
                    if is_friend == []:
                        return False
                    else:
                        await manager.send_personal_message({"id":data["id"],"type":"reply-Friend","content":{"message":"Already friend"}}, ws)
                        return True
        except Exception as e:
            print(f"Error checking is friend: {e}")
            await manager.send_personal_message({"id":data["id"],"type":"reply-Friend","content":{"message":"Error checking is friend"}}, ws)
            return False

    try:
        msg_key_check(data)
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-Friend","content":{"message":"Invalid message format"}}, ws)
        return
    
    #自分自身に対するリクエストは無効
    if user_id == data["content"]["friend_id"]:
        await manager.send_personal_message({"id":data["id"],"type":"reply-Friend","content":{"message":"Invalid friend_id"}}, ws)
        return
    
    #相手ユーザーが存在するか
    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                friend = database.fetch(cursor,"users", {"id": data["content"]["friend_id"]})
                if friend == []:
                    await manager.send_personal_message({"id":data["id"],"type":"reply-Friend","content":{"message":"Friend not found"}}, ws)
                    return
    except Exception as e:
        print(f"Error fetching friend data: {e}")
        await manager.send_personal_message({"id":data["id"],"type":"reply-Friend","content":{"message":"Error fetching friend data"}}, ws)
        return
    
    #既に友達であるか否か
    if await is_friend(user_id, data["content"]["friend_id"]):
        return
    
    is_send = False
    is_recv_request = False

    async with manager.lock:
        if data["content"]["friend_id"] in manager.friend_requests:
            is_send = user_id in manager.friend_requests[data["content"]["friend_id"]]
        else:
            manager.friend_requests[data["content"]["friend_id"]] = set()
        if user_id in manager.friend_requests:
            is_recv_request = data["content"]["friend_id"] in manager.friend_requests[user_id]
        else:
            manager.friend_requests[user_id] = set()
    
    #既に友達申請を送っている場合
    if is_send:
        await manager.send_personal_message({"id":data["id"],"type":"reply-Friend","content":{"message":"Already sent friend request"}}, ws)
        return
    
    #友達申請を受け取っている場合は友達登録
    if is_recv_request:
        try:
            with database.get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute("BEGIN")
                    if (database.insert(cursor,"friendships", {"id": user_id, "friend_id": data["content"]["friend_id"]}) and
                        database.insert(cursor,"friendships", {"id": data["content"]["friend_id"], "friend_id": user_id})):
                        conn.commit()
                        await manager.send_personal_message({"id":data["id"],"type":"reply-Friend","content":{"message":"Friend is made"}}, ws)
                    else:
                        raise Exception
        except Exception as e:
            print(f"Error making friend: {e}")
            if conn:
                conn.rollback()
                print("transaction rollback")
            await manager.send_personal_message({"id":data["id"],"type":"reply-Friend","content":{"message":"Error making friend"}}, ws)
            return
    #申請を受け取っていない場合は友達申請を送る
    else:
        async with manager.lock:
            manager.friend_requests[data["content"]["friend_id"]].add(user_id)
            #websocket通信中なら通知
            if data["content"]["friend_id"] in manager.active_connections:
                friend_ws = manager.active_connections[data["content"]["friend_id"]]
                await manager.send_personal_message({"type":"FriendRequest","content":{"friend_id":user_id}},friend_ws)
            await manager.send_personal_message({"id":data["id"],"type":"reply-Friend","content":{"message":"Friend request sent"}}, ws)

async def UnFriend(ws: WebSocket, user_id: str, data: Dict):
    """
    友達解除リクエストを処理する
    """
    def msg_key_check(data: Dict):
        content = data["content"]
        if (not "friend_id" in content.keys()):
            raise KeyError
    
    try:
        msg_key_check(data)
    except Exception as e:
        await manager.send_personal_message({"id":data["id"],"type":"reply-UnFriend","content":{"message":"Invalid message format"}}, ws)
        return
    
    #自分自身に対するリクエストは無効
    if user_id == data["content"]["friend_id"]:
        await manager.send_personal_message({"id":data["id"],"type":"reply-UnFriend","content":{"message":"Invalid friend_id"}}, ws)
        return

    try:
        with database.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                #相手ユーザーが存在するか
                friend_data = database.fetch(cursor,"users", {"id": data["content"]["friend_id"]})
                if friend_data == []:
                    await manager.send_personal_message({"id":data["id"],"type":"reply-UnFriend","content":{"message":"Friend not found"}}, ws)
                    return
                
                #友達であるか否か
                is_friend = database.fetch(cursor,"friendships", {"id": user_id, "friend_id": data["content"]["friend_id"]})
                if is_friend == []:
                    await manager.send_personal_message({"id":data["id"],"type":"reply-UnFriend","content":{"message":"Not friend"}}, ws)
                    return
                
                #友達解除
                cursor.execute("BEGIN")
                if (database.delete(cursor,"friendships", {"id": user_id, "friend_id": data["content"]["friend_id"]}) and
                    database.delete(cursor,"friendships", {"id": data["content"]["friend_id"], "friend_id": user_id})):
                    await manager.send_personal_message({"id":data["id"],"type":"reply-UnFriend","content":{"message":"Friend is removed"}}, ws)
                    conn.commit()
                else:
                    raise Exception
    except Exception as e:
        print(f"Error unfriending: {e}")
        if conn:
            conn.rollback()
            print("transaction rollback")
        await manager.send_personal_message({"id":data["id"],"type":"reply-UnFriend","content":{"message":"Error unfriending"}}, ws)
        return