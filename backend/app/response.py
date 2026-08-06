"""统一响应格式：{code, message, data}。"""
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def page_data(list_: list, total: int, page: int, page_size: int) -> dict:
    return {
        "list": list_,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def error(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error(exc.status_code, str(exc.detail)))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    msg = "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors())
    return JSONResponse(status_code=400, content=error(400, msg or "参数错误"))
