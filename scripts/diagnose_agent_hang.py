# -*- coding: utf-8 -*-
"""
诊断 Agent 卡住的问题

检查：
1. Agent 进程是否还在运行
2. 最后的日志时间
3. 网络连接状态
4. 超时配置是否生效
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import psutil  # 用于检查进程

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_agent_logs():
    """检查 Agent 日志"""
    logs_dir = project_root / "logs"
    if not logs_dir.exists():
        print("❌ 日志目录不存在")
        return
    
    # 查找最新的 agent 日志
    agent_logs = list(logs_dir.glob("agent_*.log"))
    if not agent_logs:
        print("❌ 没有找到 Agent 日志文件")
        return
    
    latest_log = max(agent_logs, key=lambda p: p.stat().st_mtime)
    print(f"📁 最新日志文件: {latest_log.name}")
    
    # 读取所有内容
    with open(latest_log, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"📝 总行数: {len(lines)}")
        
        if lines:
            # 查找启动时间
            startup_time = None
            for line in lines[:50]:  # 前50行查找启动信息
                if "ChatAgent 启动" in line or "Agent 初始化完成" in line:
                    # 提取时间戳（如果有）
                    if line.strip():
                        startup_time = line[:30]  # 前30个字符通常包含时间
                        print(f"\n⏰ Agent 启动时间: {startup_time.strip()}")
                    break
            
            if not startup_time:
                print("\n⚠️  未找到 Agent 启动信息")
            
            print("\n最后 20 行:")
            for line in lines[-20:]:
                print(f"  {line.rstrip()}")
            
            # 检查最后更新时间
            last_modified = datetime.fromtimestamp(latest_log.stat().st_mtime)
            time_since = datetime.now() - last_modified
            
            print(f"\n⏰ 最后更新时间: {last_modified.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"⏱️  距今: {time_since.total_seconds():.0f} 秒")
            
            if time_since > timedelta(minutes=2):
                print("⚠️  警告：日志超过 2 分钟未更新，Agent 可能卡住！")
            else:
                print("✅ 日志正常更新中")

def check_timeout_config():
    """检查超时配置"""
    model_file = project_root / "backend" / "agent" / "model.py"
    
    if not model_file.exists():
        print("❌ model.py 不存在")
        return
    
    content = model_file.read_text(encoding='utf-8')
    
    if 'timeout' in content and 'client_kwargs' in content:
        print("✅ 超时配置已添加到 model.py")
        # 提取超时配置行
        for i, line in enumerate(content.split('\n')):
            if 'timeout' in line and '{' in line:
                print(f"   配置: {line.strip()}")
    else:
        print("❌ 超时配置未找到")

def check_agent_processes():
    """检查正在运行的 Agent 进程"""
    print("🔍 正在运行的 Agent 进程:")
    
    agent_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('agent' in str(arg).lower() and 'main.py' in str(arg) for arg in cmdline):
                agent_count += 1
                create_time = datetime.fromtimestamp(proc.info['create_time'])
                running_time = datetime.now() - create_time
                
                print(f"\n  PID: {proc.info['pid']}")
                print(f"  启动时间: {create_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  运行时长: {running_time.total_seconds():.0f} 秒")
                print(f"  命令: {' '.join(cmdline[:5])}...")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if agent_count == 0:
        print("  ⚠️  没有找到运行中的 Agent 进程")
    else:
        print(f"\n✅ 找到 {agent_count} 个 Agent 进程")

def main():
    print("=" * 60)
    print("Agent 卡住诊断工具")
    print("=" * 60)
    
    print("\n1. 检查 Agent 进程:")
    print("-" * 60)
    check_agent_processes()
    
    print("\n2. 检查 Agent 日志:")
    print("-" * 60)
    check_agent_logs()
    
    print("\n3. 检查超时配置:")
    print("-" * 60)
    check_timeout_config()
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)
    
    print("\n💡 建议:")
    print("  1. 如果日志长时间无更新，重启 Agent 服务使超时配置生效")
    print("  2. 检查 DashScope API 服务状态")
    print("  3. 查看是否有网络波动")
    print("  4. 如果 Agent 进程启动时间早于代码修改时间，需要重启后端")

if __name__ == "__main__":
    main()
