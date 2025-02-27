from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: str  # user/assistant/system
    content: str

class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "default"
    temperature: float = 0.8
    max_tokens: int = 512
    stream: bool = False

class ChatCompletionResponse(BaseModel):
    id: str
    created: int
    model: str
    choices: list[dict]
    usage: dict
