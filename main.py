from fastapi import FastAPI
from routers import login, register, delete, refresh, websocket
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(RequestValidationError)
def validation_handler(request, exc):
    print(request)
    print(exc)
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
app.include_router(websocket.router)