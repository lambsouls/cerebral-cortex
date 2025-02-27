import os
import time
import json
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from .models import ChatCompletionRequest, ChatCompletionResponse
from .mod_loader import mod_processor

app = FastAPI()
logger = logging.getLogger("cortex")

# Configuration
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
UPSTREAM_ENDPOINT = os.getenv("SILICONFLOW_ENDPOINT", "https://api.siliconflow.cn/v1/chat/completions")

@app.on_event("startup")
async def startup():
    mod_processor.load_mods()

async def log_streaming_chunks(response_stream, request_data, request):
    """流式响应处理与实时日志"""
    is_thinking = False  # 标记是否正在输出 reasoning_content
    has_added_opening_tag = False
    # 标志位，用于跟踪是否已经处理完 reasoning_content
    has_reasoning_ended = False
    # 用于存储完整的 reasoning_content

    full_response = ""  # 用于存储完整响应以便后续 hash 处理
    full_reasoning_content = ""
    try:
        for line in response_stream.iter_content(chunk_size=1024):
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data:'):
                    json_str = decoded_line[5:].strip()
                    if json_str == "[DONE]":  # 检查是否为流式响应结束信号
                        print("\n[DONE]")
                        break
                if json_str:  # 仅当字符串非空时尝试解析
                    try:
                        chunk = json.loads(json_str)
                        if 'choices' in chunk:  # 确保响应包含 choices 字段
                            reasoning_content = chunk['choices'][0]['delta'].get('reasoning_content', '')
                            content = chunk['choices'][0]['delta'].get('content', '')
                            if 'choices' in chunk:  # 确保响应包含 choices 字段
                                reasoning_content = chunk['choices'][0]['delta'].get('reasoning_content', '')
                                content = chunk['choices'][0]['delta'].get('content', '')
                                if reasoning_content:
                                    # 如果是第一次输出 reasoning_content，添加开头标签
                                    if not has_added_opening_tag:
                                        print(f"<think>\n{reasoning_content}", end='', flush=True)
                                        has_added_opening_tag = True
                                    else:
                                        print(reasoning_content, end='', flush=True)
                                    full_reasoning_content += reasoning_content
                                elif not has_reasoning_ended and full_reasoning_content:
                                    # reasoning_content 结束，输出结尾标签
                                    print("</think>", end='', flush=True)
                                    has_reasoning_ended = True
                                if content:
                                    print(content, end='', flush=True)
                                    full_response += content
                                
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"解析 chunk 时出错：{e}") 
                    yield decoded_line  # 实时返回给客户端

    except UnicodeDecodeError as e:
        print(f"解码 line 时出错：{e}")

    response_stream.close()

    print(f"\n💠 流式传输完成，总长度: {len(full_response)} bytes")
    await mod_processor.run_postprocess({
        "type": "stream",
        "original_request": request_data,
        "response": full_response
    }, request)


@app.post("/v1/chat/completions")
async def handle_request(request: Request):
    # Step 1: 原始请求记录
    request_data = await request.json()
    print(f"\n🎯 收到请求 ({'stream' if request_data.get('stream', False) else 'static'})")
    print("┏━━ 原始请求 ━━━━━━━━━━━")
    print(json.dumps(request_data, indent=2, ensure_ascii=False))
    print("┗━━━━━━━━━━━━━━━━━━━━━━")

    # Step 2: 预处理链
    processed_data = await mod_processor.run_preprocess(request_data, request)
    
    # Step 3: 分发请求
    try:
        if processed_data.get("stream", False):
            # 流式请求
            print("\n🌀 进入流式处理模式")
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
            print(f"\n📦 收到静态响应 ({len(response.text)} bytes)")
            response_data = response.json()
            print("┏━━ 原始响应 ━━━━━━━━━")
            print(json.dumps(response_data, indent=2, ensure_ascii=False))
            print("┗━━━━━━━━━━━━━━━━━━━")

            # 后处理
            post_data = await mod_processor.run_postprocess({
                "type": "static",
                "original_request": request_data,
                "response": response_data
            }, request=request)
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