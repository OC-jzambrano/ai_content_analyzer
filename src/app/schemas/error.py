from pydantic import BaseModel

class ErrorSchema(BaseModel):
    stage: str
    message: str
    retryable: bool = False