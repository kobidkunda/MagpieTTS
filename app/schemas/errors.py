"""Central error codes and exception class for the Magpie TTS server."""

from typing import Optional, Dict, Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    type: str = "validation_error"
    request_id: Optional[str] = None
    retryable: bool = False
    details: Optional[Dict[str, Any]] = None


class ApiError(BaseModel):
    error: ApiErrorDetail


class ErrorCodes:
    INVALID_REQUEST = "INVALID_REQUEST"
    EMPTY_TEXT = "EMPTY_TEXT"
    TEXT_TOO_LONG = "TEXT_TOO_LONG"
    INVALID_LANGUAGE = "INVALID_LANGUAGE"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    INVALID_VOICE = "INVALID_VOICE"
    INVALID_FORMAT = "INVALID_FORMAT"
    INVALID_SAMPLE_RATE = "INVALID_SAMPLE_RATE"
    INVALID_SPEED = "INVALID_SPEED"
    MODEL_NOT_LOADED = "MODEL_NOT_LOADED"
    MODEL_LOADING = "MODEL_LOADING"
    MODEL_SWITCHING = "MODEL_SWITCHING"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    CODEC_NOT_READY = "CODEC_NOT_READY"
    QUEUE_FULL = "QUEUE_FULL"
    CONCURRENCY_LIMIT = "CONCURRENCY_LIMIT"
    SYNTHESIS_TIMEOUT = "SYNTHESIS_TIMEOUT"
    SYNTHESIS_CANCELLED = "SYNTHESIS_CANCELLED"
    SYNTHESIS_FAILED = "SYNTHESIS_FAILED"
    CUDA_OOM = "CUDA_OOM"
    CUDA_ERROR = "CUDA_ERROR"
    ENCODER_FAILED = "ENCODER_FAILED"
    RESAMPLER_FAILED = "RESAMPLER_FAILED"
    WEBSOCKET_PROTOCOL_ERROR = "WEBSOCKET_PROTOCOL_ERROR"
    WEBSOCKET_SESSION_NOT_FOUND = "WEBSOCKET_SESSION_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


HTTP_STATUS = {
    ErrorCodes.INVALID_REQUEST: 400,
    ErrorCodes.EMPTY_TEXT: 422,
    ErrorCodes.TEXT_TOO_LONG: 422,
    ErrorCodes.INVALID_LANGUAGE: 422,
    ErrorCodes.UNSUPPORTED_LANGUAGE: 422,
    ErrorCodes.INVALID_VOICE: 422,
    ErrorCodes.INVALID_FORMAT: 422,
    ErrorCodes.INVALID_SAMPLE_RATE: 422,
    ErrorCodes.INVALID_SPEED: 422,
    ErrorCodes.MODEL_NOT_LOADED: 503,
    ErrorCodes.MODEL_LOADING: 503,
    ErrorCodes.MODEL_SWITCHING: 503,
    ErrorCodes.MODEL_LOAD_FAILED: 503,
    ErrorCodes.CODEC_NOT_READY: 503,
    ErrorCodes.QUEUE_FULL: 429,
    ErrorCodes.CONCURRENCY_LIMIT: 429,
    ErrorCodes.SYNTHESIS_TIMEOUT: 504,
    ErrorCodes.SYNTHESIS_CANCELLED: 400,
    ErrorCodes.SYNTHESIS_FAILED: 500,
    ErrorCodes.CUDA_OOM: 503,
    ErrorCodes.CUDA_ERROR: 500,
    ErrorCodes.ENCODER_FAILED: 500,
    ErrorCodes.RESAMPLER_FAILED: 500,
    ErrorCodes.WEBSOCKET_PROTOCOL_ERROR: 400,
    ErrorCodes.WEBSOCKET_SESSION_NOT_FOUND: 404,
    ErrorCodes.INTERNAL_ERROR: 500,
}


ERROR_TYPES = {
    "INVALID_REQUEST": "validation_error",
    "EMPTY_TEXT": "validation_error",
    "TEXT_TOO_LONG": "validation_error",
    "INVALID_LANGUAGE": "validation_error",
    "UNSUPPORTED_LANGUAGE": "validation_error",
    "INVALID_VOICE": "validation_error",
    "INVALID_FORMAT": "validation_error",
    "INVALID_SAMPLE_RATE": "validation_error",
    "INVALID_SPEED": "validation_error",
    "MODEL_NOT_LOADED": "model_error",
    "MODEL_LOADING": "model_error",
    "MODEL_SWITCHING": "model_error",
    "MODEL_LOAD_FAILED": "model_error",
    "CODEC_NOT_READY": "model_error",
    "QUEUE_FULL": "rate_limit_error",
    "CONCURRENCY_LIMIT": "rate_limit_error",
    "SYNTHESIS_TIMEOUT": "synthesis_error",
    "SYNTHESIS_CANCELLED": "synthesis_error",
    "SYNTHESIS_FAILED": "synthesis_error",
    "CUDA_OOM": "model_error",
    "CUDA_ERROR": "model_error",
    "ENCODER_FAILED": "encoding_error",
    "RESAMPLER_FAILED": "encoding_error",
    "WEBSOCKET_PROTOCOL_ERROR": "websocket_error",
    "WEBSOCKET_SESSION_NOT_FOUND": "websocket_error",
    "INTERNAL_ERROR": "internal_error",
}


class ApiException(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False,
                 details: dict | None = None, status: int | None = None,
                 error_type: str | None = None):
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details
        self.status = status or HTTP_STATUS.get(code, 500)
        self.error_type = error_type or ERROR_TYPES.get(code, "validation_error")
        super().__init__(message)


def error_payload(exc: ApiException, request_id: str | None) -> dict:
    body = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "type": exc.error_type,
            "request_id": request_id,
            "retryable": exc.retryable,
        }
    }
    if exc.details is not None:
        body["error"]["details"] = exc.details
    return body


async def api_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(status_code=exc.status, content=error_payload(exc, request_id))
