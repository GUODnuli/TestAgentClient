#!/usr/bin/env python
"""
MCP 接口测试智能体 - 命令行工具

提供无头模式支持，方便集成到 CI/CD。
"""

import argparse
import sys
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

console = Console()

API_BASE = "http://localhost:8000/api"


def create_task(args):
    """创建测试任务"""
    console.print("[bold cyan]创建测试任务...[/bold cyan]")
    
    response = requests.post(f"{API_BASE}/tasks", json={
        "task_type": "api_test",
        "document_path": args.document,
        "config": {
            "test_engine": args.engine,
            "parallel_execution": args.parallel
        }
    })
    
    if response.status_code == 200:
        data = response.json()
        if data["success"]:
            console.print(f"[green]✓[/green] 任务创建成功")
            console.print(f"[yellow]任务ID:[/yellow] {data['task_id']}")
            return data["task_id"]
    
    console.print("[red]✗ 任务创建失败[/red]")
    return None


def get_status(args):
    """查询任务状态"""
    response = requests.get(f"{API_BASE}/tasks/{args.task_id}")
    
    if response.status_code == 200:
        data = response.json()["data"]
        
        panel = Panel(
            f"[cyan]状态:[/cyan] {data['status']}\n"
            f"[cyan]当前阶段:[/cyan] {data.get('current_state', 'N/A')}\n"
            f"[cyan]创建时间:[/cyan] {data['created_at']}\n"
            f"[cyan]更新时间:[/cyan] {data['updated_at']}",
            title=f"任务 {args.task_id}",
            border_style="cyan"
        )
        console.print(panel)
    else:
        console.print("[red]✗ 获取任务状态失败[/red]")


def list_tasks(args):
    """列出任务列表"""
    response = requests.get(f"{API_BASE}/tasks", params={"limit": args.limit})
    
    if response.status_code == 200:
        tasks = response.json()["data"]["tasks"]
        
        table = Table(title="任务列表")
        table.add_column("任务ID", style="cyan")
        table.add_column("类型", style="magenta")
        table.add_column("状态", style="green")
        table.add_column("创建时间", style="yellow")
        
        for task in tasks:
            table.add_row(
                task["task_id"][:8] + "...",
                task["type"],
                task["status"],
                task["created_at"]
            )
        
        console.print(table)
    else:
        console.print("[red]✗ 获取任务列表失败[/red]")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="MCP 接口测试智能体 - 命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # create 命令
    create_parser = subparsers.add_parser("create", help="创建测试任务")
    create_parser.add_argument("document", help="接口文档路径")
    create_parser.add_argument("--engine", choices=["requests", "httprunner", "auto"], 
                             default="auto", help="测试引擎")
    create_parser.add_argument("--parallel", action="store_true", help="启用并发执行")
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查询任务状态")
    status_parser.add_argument("task_id", help="任务ID")
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出任务")
    list_parser.add_argument("--limit", type=int, default=10, help="最大数量")
    
    args = parser.parse_args()
    
    if args.command == "create":
        create_task(args)
    elif args.command == "status":
        get_status(args)
    elif args.command == "list":
        list_tasks(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
#!/usr/bin/env python
"""
MCP 接口测试智能体 - 命令行工具

提供无头模式支持，方便集成到 CI/CD。
"""

import argparse
import sys
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

console = Console()

API_BASE = "http://localhost:8000/api"


def create_task(args):
    """创建测试任务"""
    console.print("[bold cyan]创建测试任务...[/bold cyan]")
    
    response = requests.post(f"{API_BASE}/tasks", json={
        "task_type": "api_test",
        "document_path": args.document,
        "config": {
            "test_engine": args.engine,
            "parallel_execution": args.parallel
        }
    })
    
    if response.status_code == 200:
        data = response.json()
        if data["success"]:
            console.print(f"[green]✓[/green] 任务创建成功")
            console.print(f"[yellow]任务ID:[/yellow] {data['task_id']}")
            return data["task_id"]
    
    console.print("[red]✗ 任务创建失败[/red]")
    return None


def get_status(args):
    """查询任务状态"""
    response = requests.get(f"{API_BASE}/tasks/{args.task_id}")
    
    if response.status_code == 200:
        data = response.json()["data"]
        
        panel = Panel(
            f"[cyan]状态:[/cyan] {data['status']}\n"
            f"[cyan]当前阶段:[/cyan] {data.get('current_state', 'N/A')}\n"
            f"[cyan]创建时间:[/cyan] {data['created_at']}\n"
            f"[cyan]更新时间:[/cyan] {data['updated_at']}",
            title=f"任务 {args.task_id}",
            border_style="cyan"
        )
        console.print(panel)
    else:
        console.print("[red]✗ 获取任务状态失败[/red]")


def list_tasks(args):
    """列出任务列表"""
    response = requests.get(f"{API_BASE}/tasks", params={"limit": args.limit})
    
    if response.status_code == 200:
        tasks = response.json()["data"]["tasks"]
        
        table = Table(title="任务列表")
        table.add_column("任务ID", style="cyan")
        table.add_column("类型", style="magenta")
        table.add_column("状态", style="green")
        table.add_column("创建时间", style="yellow")
        
        for task in tasks:
            table.add_row(
                task["task_id"][:8] + "...",
                task["type"],
                task["status"],
                task["created_at"]
            )
        
        console.print(table)
    else:
        console.print("[red]✗ 获取任务列表失败[/red]")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="MCP 接口测试智能体 - 命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # create 命令
    create_parser = subparsers.add_parser("create", help="创建测试任务")
    create_parser.add_argument("document", help="接口文档路径")
    create_parser.add_argument("--engine", choices=["requests", "httprunner", "auto"], 
                             default="auto", help="测试引擎")
    create_parser.add_argument("--parallel", action="store_true", help="启用并发执行")
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查询任务状态")
    status_parser.add_argument("task_id", help="任务ID")
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出任务")
    list_parser.add_argument("--limit", type=int, default=10, help="最大数量")
    
    args = parser.parse_args()
    
    if args.command == "create":
        create_task(args)
    elif args.command == "status":
        get_status(args)
    elif args.command == "list":
        list_tasks(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
