# instruction_handler.py

def parse_instruction_message(message: str) -> tuple:
    """
    解析指令消息，格式为 "/<command> <额外信息>"。
    返回指令和额外信息。
    
    Args:
        message (str): 输入的消息内容。
        
    Returns:
        tuple: (command, extra_info)，如果没有指令，则返回 (None, None)。
    """
    message = message.strip()
    if message.startswith("/"):
        # 提取指令和额外信息
        parts = message.split(maxsplit=1)
        command = parts[0]
        extra_info = parts[1] if len(parts) > 1 else ""
        return command, extra_info
    return None, None


def handle_instruction(message: str) -> dict:
    """
    处理指令的函数。如果消息是指令，返回处理结果；
    否则返回 None，表示消息不是指令。
    
    Args:
        message (str): 输入的消息内容，格式为 "/<command> <额外信息>"。
        
    Returns:
        dict: 指令处理结果，包含指令响应和是否需要跳过 API 调用。
             如果不是指令，返回 None。
    """
    # 定义指令列表
    INSTRUCTIONS = {
        "/skip": "跳过信息，不发送给 API"
    }

    # 解析指令消息
    command, extra_info = parse_instruction_message(message)

    # 判断是否为指令
    if command and command in INSTRUCTIONS:
        response = {
            "instruction": command,
            "result": INSTRUCTIONS[command],
            "extra_info": extra_info,  # 额外信息作为字符串返回
            "skip_api": True  # 标记是否需要跳过 API 调用
        }
        return response
    
    return None