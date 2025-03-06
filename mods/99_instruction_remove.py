async def parse_instruction_message(message: str) -> tuple:
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

async def preprocess(data: dict, request):
    """预处理"""
    INSTRUCTIONS = {
        "/skip": "跳过信息，不发送给 API",
        "/instruction": "instruction_result",
    }

    messages = data.get("messages", [])
    last_message = messages[-1]["content"] if messages else ""

    # 确保 last_message 是字符串
    if isinstance(last_message, dict):
        last_message = str(last_message)

    command, extra_info = await parse_instruction_message(last_message)
    if command and command in INSTRUCTIONS:
        print(f"\ninstruction_remove发现待执行指令: {last_message} , instruction_remove即将结束开始执行指令...\n")
        return data
    else:
        # 非指令
        print(f"\ninstruction_remove未发现待执行指令 , 开始去除无用instruction_和无用instruction_result...")
        messages_to_remove = []  # 记录需要删除的消息
        # 遍历 messages 列表
        for message in messages:
            # 确保 message["content"] 是字符串
            content = message["content"]
            if isinstance(content, dict):
                content = str(content)

            # 判断是否删除当前消息
            command, extra_info = await parse_instruction_message(content)
            if command and command in INSTRUCTIONS:
                messages_to_remove.append(message)
                print(f"发现一条无用instruction_或无用的instruction_result: {message}")

        # 删除需要移除的消息
        for message in messages_to_remove:
            messages.remove(message)
            print(f"移除了一条无用instruction_或无用的instruction_result: {message}")

        # 更新 data 中的 messages
        data["messages"] = messages
        print("")
        return data

async def postprocess(data: dict, request):
    """后处理"""
    print(f"\n后处理...")
    return data