from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from routers import login, register, delete, refresh
from typing import List
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://" + window.location.host + "/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>

"""
"""
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            await ws.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        manager.disconnect(ws)
        await manager.broadcast(f"Client left the chat")
"""

@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    error_lists = []
    for e in exc.errors():#エラーメッセージの抽出
        if 'ctx' in e and 'error' in e['ctx']:
            error_obj = e['ctx']['error']
            if isinstance(error_obj, ValueError) and hasattr(error_obj, 'args'):
                error_list = error_obj.args[0]
                if isinstance(error_list, list):
                    for error_msg in error_list:
                        error_ = {}
                        error_["loc"] = e["loc"][-1]
                        error_["msg"] = error_msg
                        error_lists.append(error_)
        else:
            error = {}
            error["loc"] = e["loc"][-1]
            error["msg"] = e["msg"]
            error_lists.append(error)
    for e in error_lists:
        print(e)

    return JSONResponse(
        status_code=400,
        content={"detail": error_lists}
    )

app.include_router(login.router)
app.include_router(register.router)
app.include_router(delete.router)
app.include_router(refresh.router)