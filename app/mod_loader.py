import importlib.util
import os
from pathlib import Path
from typing import Callable, List, Dict, Any
import asyncio
import time

class ModProcessor:
    def __init__(self):
        self.modules: List[Dict[str, Callable]] = []
        self.mod_order: List[str] = []
    
    def load_mods(self):
        mod_dir = Path(__file__).parent.parent / "mods"
        for mod_file in sorted(mod_dir.glob("*.py")):
            mod_name = mod_file.stem
            spec = importlib.util.spec_from_file_location(mod_name, mod_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if not (hasattr(module, 'preprocess') and hasattr(module, 'postprocess')):
                print(f"模块 {mod_name} 缺少 preprocess/postprocess 函数，已跳过")
                continue
                
            self.modules.append({
                "name": mod_name,
                "pre": module.preprocess,
                "post": module.postprocess
            })
            self.mod_order.append(mod_name)
            print(f"加载模块: {mod_name} (preprocess+postprocess)")
    
    async def run_preprocess(self, data: dict, request: Any) -> dict:
        print(f"\n开始预处理链路 [{len(self.modules)} modules]")
        for mod in self.modules:
            start = time.monotonic()
            print(f"前置处理 [{mod['name']}]")
            try:
                data = await mod['pre'](data, request)
                cost = (time.monotonic() - start) * 1000
                print(f"完成处理 [{mod['name']}] ({cost:.2f}ms)")
            except Exception as e:
                print(f"模块 {mod['name']} 预处理错误: {str(e)}")
        return data
    
    async def run_postprocess(self, data: dict, original_request: Any) -> dict:
        print(f"\n开始后处理链路 [{len(self.modules)} modules]")
        for mod in reversed(self.modules):
            start = time.monotonic()
            print(f"后置处理 [{mod['name']}]")
            try:
                data = await mod['post'](data, original_request)
                cost = (time.monotonic() - start) * 1000
                print(f"完成处理 [{mod['name']}] ({cost:.2f}ms)")
            except Exception as e:
                print(f"模块 {mod['name']} 后处理错误: {str(e)}")
        return data

mod_processor = ModProcessor()
