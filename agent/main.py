# -*- coding: utf-8 -*-
"""
ChatAgent 入口文件 (DEPRECATED)

此文件已弃用，所有功能已迁移至 coordinator_main.py。
为保持向后兼容性，此文件会自动重定向到 coordinator_main.py。

新的调用方式：
  python coordinator_main.py --mode direct   # 单 Agent 模式（原 main.py 行为）
  python coordinator_main.py --mode coordinator  # 多 Worker 协调模式
"""
import asyncio
import sys
import warnings
from pathlib import Path

# 发出弃用警告
warnings.warn(
    "main.py 已弃用，请使用 coordinator_main.py。"
    "此文件将在未来版本中移除。",
    DeprecationWarning,
    stacklevel=2
)

# 确保可以导入 coordinator_main
project_root = Path(__file__).parent.parent
agent_dir = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

# 重定向到 coordinator_main
from coordinator_main import main

if __name__ == '__main__':
    print("[DEPRECATED] main.py 已弃用，正在重定向到 coordinator_main.py...")
    asyncio.run(main())
