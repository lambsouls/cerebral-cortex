import os
import time
import json
import logging
import asyncio
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from .models import ChatCompletionRequest, ChatCompletionResponse
from .mod_loader import mod_processor
from fastapi.middleware.cors import CORSMiddleware
from .instruction_handler import handle_instruction

app = FastAPI()
logger = logging.getLogger("cortex")

# 允许所有来源的跨域请求（生产环境中应指定具体的来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)
# Configuration
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
UPSTREAM_ENDPOINT = os.getenv("SILICONFLOW_ENDPOINT", "https://api.siliconflow.cn/v1/chat/completions")

@app.on_event("startup")
async def startup():
    mod_processor.load_mods()

async def log_streaming_chunks(response_stream, request_data, request):
    """流式响应处理与实时日志"""
    is_thinking = False
    has_added_opening_tag = False
    has_reasoning_ended = False
    full_response = ""
    full_reasoning_content = ""
    try:
        for line in response_stream.iter_content(chunk_size=1024):
            if await request.is_disconnected():  # 检测客户端是否断开
                print("\n客户端已断开，停止流式传输")
                break

            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data:'):
                    json_str = decoded_line[5:].strip()
                    if json_str == "[DONE]":
                        print("\n[DONE]")
                        break

                if json_str:
                    try:
                        chunk = json.loads(json_str)
                        if 'choices' in chunk:
                            reasoning_content = chunk['choices'][0]['delta'].get('reasoning_content', '')
                            content = chunk['choices'][0]['delta'].get('content', '')
                            if reasoning_content:
                                if not has_added_opening_tag:
                                    print(f"<think>\n{reasoning_content}", end='', flush=True)
                                    has_added_opening_tag = True
                                else:
                                    print(reasoning_content, end='', flush=True)
                                full_reasoning_content += reasoning_content
                            elif not has_reasoning_ended and full_reasoning_content:
                                print("</think>", end='', flush=True)
                                has_reasoning_ended = True
                            if content:
                                print(content, end='', flush=True)
                                full_response += content

                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"解析 chunk 时出错：{e}")
                    #print(json.dumps(decoded_line, indent=2, ensure_ascii=False))
                    yield decoded_line

    except UnicodeDecodeError as e:
        print(f"解码 line 时出错：{e}")

    response_stream.close()

    print(f"\n流式传输完成，总长度: {len(full_response)} bytes")
    await mod_processor.run_postprocess({
        "type": "stream",
        "original_request": request_data,
        "response": full_response
    }, request)

async def generate_stream_chunks(instruction_result):
    """
    生成符合客户端格式的流式数据
    """
    # 初始 chunk：设置角色
    initial_chunk = {
        "id": "chatcmpl-12345",  # 唯一的 ID
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "deepseek-ai/DeepSeek-R1",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": None,
                    "reasoning_content": ""
                },
                "finish_reason": None,
                "content_filter_results": {
                    "hate": {"filtered": False},
                    "self_harm": {"filtered": False},
                    "sexual": {"filtered": False},
                    "violence": {"filtered": False}
                }
            }
        ],
        "system_fingerprint": "",
        "usage": {
            "prompt_tokens": 16,
            "completion_tokens": 0,
            "total_tokens": 16
        }
    }
    yield f"data: {json.dumps(initial_chunk)}\n\n"

    # 生成内容的 chunks
    content = "/instruction \n"f"指令: {instruction_result['instruction']}\n结果: {instruction_result['result']}\n额外信息: {instruction_result['extra_info']}"
    for i in range(0, len(content), 2):  # 每次返回 2 个字符
        chunk = {
            "id": "chatcmpl-12345",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "deepseek-ai/DeepSeek-R1",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "reasoning_content": None,
                        "content": content[i:i+2]  # 每次返回部分内容
                    },
                    "finish_reason": None,
                    "content_filter_results": {
                        "hate": {"filtered": False},
                        "self_harm": {"filtered": False},
                        "sexual": {"filtered": False},
                        "violence": {"filtered": False}
                    }
                }
            ],
            "system_fingerprint": "",
            "usage": {
                "prompt_tokens": 16,
                "completion_tokens": i + 1,
                "total_tokens": 16 + i + 1
            }
        }
        yield f"data: {json.dumps(chunk)}\n\n"

    # 最后一个 chunk：结束标志
    final_chunk = {
        "id": "chatcmpl-12345",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "deepseek-ai/DeepSeek-R1",
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
                "content_filter_results": {
                    "hate": {"filtered": False},
                    "self_harm": {"filtered": False},
                    "sexual": {"filtered": False},
                    "violence": {"filtered": False}
                }
            }
        ],
        "system_fingerprint": "",
        "usage": {
            "prompt_tokens": 16,
            "completion_tokens": len(content),
            "total_tokens": 16 + len(content)
        }
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"


@app.post("/v1/chat/completions")
async def handle_request(request: Request):
    # Step 1: 原始请求记录
    request_data = await request.json()
    print(f"\n收到请求 ({'stream' if request_data.get('stream', False) else 'static'})")
    print("┏━━ 原始请求 ━━━━━━━━━━━")
    print(json.dumps(request_data, indent=2, ensure_ascii=False))
    print("┗━━━━━━━━━━━━━━━━━━━━━━━")

    # Step 2: 预处理链
    processed_data = await mod_processor.run_preprocess(request_data, request)
 
    # Step 3: 指令处理
    # 获取消息内容和上下文信息
    messages = processed_data.get("messages", [])
    last_message = messages[-1]["content"] if messages else ""
    
    # 调用指令处理函数
    instruction_result = handle_instruction(last_message)
    
    # 如果是指令，返回指令处理结果
    if instruction_result and instruction_result.get("skip_api", False):
        
        # 构造与 API 输出一致的响应格式
        print("┏━━ 指令信息 ━━━━━━━━━━━")
        print(f"指令: {instruction_result['instruction']}")
        print(f"结果: {instruction_result['result']}")
        print(f"额外信息: {instruction_result['extra_info']}")
        print("┗━━━━━━━━━━━━━━━━━━━━━━━")
        
        is_stream = request_data.get("stream", False)
        #如果是非流式输出，返回非流式输出指令处理结果
        if not is_stream:
            response_data = {
                                "choices": [
                                {
                                    "index": 0,
                                    "message": {
                                    "role": "assistant",
                                    "content":"/instruction \n"
                                        f"指令: {instruction_result['instruction']}\n"
                                        f"结果: {instruction_result['result']}\n"
                                        f"额外信息: {instruction_result['extra_info']}"
                                    },
                                    "finish_reason": "stop"
                                }
                                ],
                            }
            #print(json.dumps(response_data, indent=2, ensure_ascii=False))
            # 返回与 API 一致的响应
            return response_data
        # 流式模式
        else:
            return StreamingResponse(
                generate_stream_chunks(instruction_result),
                media_type="text/event-stream"
            )

    # Step 4: 分发请求
    try:
        if processed_data.get("stream", False):
            # 流式请求
            print("\n进入流式处理模式")
            response = requests.post(
                UPSTREAM_ENDPOINT,
                json=processed_data,
                headers={
                    "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                    "Content-Type": "application/json"
                },
                stream=True
            )
            response.raise_for_status()
            return StreamingResponse(
                log_streaming_chunks(response, request_data, request),
                media_type="text/event-stream"
            )
        else:
            # 静态请求
            response = requests.post(
                UPSTREAM_ENDPOINT,
                json=processed_data,
                headers={
                    "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            print(f"\n收到静态响应 ({len(response.text)} bytes)")
            response_data = response.json()
            print("┏━━ 原始响应 ━━━━━━━━━")
            print(json.dumps(response_data, indent=2, ensure_ascii=False))
            print("┗━━━━━━━━━━━━━━━━━━━━━")

            # 后处理
            post_data = await mod_processor.run_postprocess({
                "type": "static",
                "original_request": request_data,
                "response": response_data
            }, request)
            return post_data["response"]
    except requests.exceptions.HTTPError as e:
        logger.error(f"上游API错误: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=503, detail="服务暂时不可用")
    except requests.exceptions.RequestException as e:
        logger.error(f"上游API连接失败: {str(e)}")
        raise HTTPException(status_code=503, detail="上游服务不可用")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        env_file=".env"
    )