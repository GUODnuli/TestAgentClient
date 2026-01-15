"""
测试报告生成器

生成 Markdown 和 HTML 格式的测试报告。
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
from jinja2 import Template

from backend.common.test_models import TestReport, TestResult, TestCaseStatus
from backend.common.logger import Logger


class ReportGenerator:
    """
    测试报告生成器
    
    功能：
    - 生成 Markdown 格式报告
    - 生成 HTML 格式报告（带样式）
    - 支持自定义模板
    - 包含详细的测试结果和统计图表
    """
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
    
    def generate_markdown(self, report: TestReport, output_path: Optional[Path] = None) -> str:
        """
        生成 Markdown 格式报告
        
        Args:
            report: 测试报告对象
            output_path: 输出路径（可选）
            
        Returns:
            Markdown 文本
        """
        self.logger.info(
            f"开始生成 Markdown 报告 | 任务ID: {report.task_id}",
            task_id=report.task_id
        )
        
        markdown = self._build_markdown_content(report)
        
        if output_path:
            output_path.write_text(markdown, encoding="utf-8")
            self.logger.info(
                f"Markdown 报告已保存 | 路径: {output_path}",
                path=str(output_path)
            )
        
        return markdown
    
    def generate_html(self, report: TestReport, output_path: Optional[Path] = None) -> str:
        """
        生成 HTML 格式报告
        
        Args:
            report: 测试报告对象
            output_path: 输出路径（可选）
            
        Returns:
            HTML 文本
        """
        self.logger.info(
            f"开始生成 HTML 报告 | 任务ID: {report.task_id}",
            task_id=report.task_id
        )
        
        html = self._build_html_content(report)
        
        if output_path:
            output_path.write_text(html, encoding="utf-8")
            self.logger.info(
                f"HTML 报告已保存 | 路径: {output_path}",
                path=str(output_path)
            )
        
        return html
    
    def _build_markdown_content(self, report: TestReport) -> str:
        """构建 Markdown 报告内容"""
        lines = []
        
        # 标题
        lines.append(f"# 测试报告")
        lines.append("")
        lines.append(f"**任务ID**: `{report.task_id}`  ")
        lines.append(f"**生成时间**: {report.generated_at}  ")
        lines.append(f"**总耗时**: {report.total_duration:.2f}秒  ")
        lines.append("")
        
        # 执行摘要
        lines.append("## 📊 执行摘要")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 总用例数 | {report.total_count} |")
        lines.append(f"| ✅ 通过 | {report.passed_count} |")
        lines.append(f"| ❌ 失败 | {report.failed_count} |")
        lines.append(f"| ⚠️ 错误 | {report.error_count} |")
        lines.append(f"| ⏭️ 跳过 | {report.skipped_count} |")
        lines.append(f"| 📈 通过率 | **{report.pass_rate}%** |")
        lines.append("")
        
        # 进度条
        lines.append(self._build_progress_bar(report))
        lines.append("")
        
        # 最慢用例
        if report.slowest_testcases:
            lines.append("## ⏱️ 最慢用例 Top 10")
            lines.append("")
            lines.append("| 排名 | 接口名称 | 用例ID | 耗时(秒) |")
            lines.append("|------|----------|--------|----------|")
            for i, slow_case in enumerate(report.slowest_testcases, 1):
                lines.append(
                    f"| {i} | {slow_case['interface_name']} | "
                    f"`{slow_case['testcase_id'][:8]}...` | "
                    f"{slow_case['duration']:.3f} |"
                )
            lines.append("")
        
        # 错误模式
        if report.error_patterns:
            lines.append("## 🔍 错误模式分析")
            lines.append("")
            lines.append("| 错误模式 | 出现次数 | 示例用例 |")
            lines.append("|----------|----------|----------|")
            for pattern in report.error_patterns[:10]:  # 只显示前10个
                lines.append(
                    f"| {pattern['pattern'][:50]}... | "
                    f"{pattern['count']} | "
                    f"`{pattern['example_id'][:8]}...` |"
                )
            lines.append("")
        
        # 详细结果
        lines.append("## 📋 详细测试结果")
        lines.append("")
        
        # 按状态分组
        passed_results = [r for r in report.testcase_results if r.status == TestCaseStatus.PASSED]
        failed_results = [r for r in report.testcase_results if r.status == TestCaseStatus.FAILED]
        error_results = [r for r in report.testcase_results if r.status == TestCaseStatus.ERROR]
        
        # 失败用例
        if failed_results:
            lines.append("### ❌ 失败用例")
            lines.append("")
            for result in failed_results:
                lines.extend(self._format_test_result(result))
            lines.append("")
        
        # 错误用例
        if error_results:
            lines.append("### ⚠️ 错误用例")
            lines.append("")
            for result in error_results:
                lines.extend(self._format_test_result(result))
            lines.append("")
        
        # 通过用例（折叠显示）
        if passed_results:
            lines.append("### ✅ 通过用例")
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>点击展开查看通过的用例详情</summary>")
            lines.append("")
            for result in passed_results:
                lines.extend(self._format_test_result(result, brief=True))
            lines.append("</details>")
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_html_content(self, report: TestReport) -> str:
        """构建 HTML 报告内容"""
        template_str = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>测试报告 - {{ report.task_id }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .content { padding: 30px; }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .summary-card h3 { font-size: 0.9em; color: #666; margin-bottom: 10px; }
        .summary-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }
        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
        }
        .progress-fill {
            height: 100%;
            display: flex;
            transition: width 0.3s ease;
        }
        .progress-passed { background: #4caf50; }
        .progress-failed { background: #f44336; }
        .progress-error { background: #ff9800; }
        .progress-skipped { background: #9e9e9e; }
        .section {
            margin: 30px 0;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 8px;
        }
        .section h2 {
            color: #667eea;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }
        th {
            background: #667eea;
            color: white;
            font-weight: 600;
        }
        tr:hover { background: #f5f5f5; }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
        }
        .status-passed { background: #4caf50; color: white; }
        .status-failed { background: #f44336; color: white; }
        .status-error { background: #ff9800; color: white; }
        .status-skipped { background: #9e9e9e; color: white; }
        .test-detail {
            background: white;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #667eea;
            border-radius: 4px;
        }
        .test-detail h4 { color: #333; margin-bottom: 10px; }
        .test-detail pre {
            background: #f5f5f5;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.9em;
        }
        .footer {
            text-align: center;
            padding: 20px;
            background: #f5f5f5;
            color: #666;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 测试报告</h1>
            <p>任务ID: {{ report.task_id }}</p>
            <p>生成时间: {{ report.generated_at }}</p>
        </div>
        
        <div class="content">
            <div class="summary">
                <div class="summary-card">
                    <h3>总用例数</h3>
                    <div class="value">{{ report.total_count }}</div>
                </div>
                <div class="summary-card">
                    <h3>✅ 通过</h3>
                    <div class="value" style="color: #4caf50;">{{ report.passed_count }}</div>
                </div>
                <div class="summary-card">
                    <h3>❌ 失败</h3>
                    <div class="value" style="color: #f44336;">{{ report.failed_count }}</div>
                </div>
                <div class="summary-card">
                    <h3>⚠️ 错误</h3>
                    <div class="value" style="color: #ff9800;">{{ report.error_count }}</div>
                </div>
                <div class="summary-card">
                    <h3>📈 通过率</h3>
                    <div class="value">{{ report.pass_rate }}%</div>
                </div>
                <div class="summary-card">
                    <h3>⏱️ 总耗时</h3>
                    <div class="value" style="font-size: 1.5em;">{{ "%.2f"|format(report.total_duration) }}s</div>
                </div>
            </div>
            
            <div class="progress-bar">
                <div class="progress-fill">
                    {% if report.passed_count > 0 %}
                    <div class="progress-passed" style="width: {{ (report.passed_count / report.total_count * 100) }}%;"></div>
                    {% endif %}
                    {% if report.failed_count > 0 %}
                    <div class="progress-failed" style="width: {{ (report.failed_count / report.total_count * 100) }}%;"></div>
                    {% endif %}
                    {% if report.error_count > 0 %}
                    <div class="progress-error" style="width: {{ (report.error_count / report.total_count * 100) }}%;"></div>
                    {% endif %}
                </div>
            </div>
            
            {% if report.slowest_testcases %}
            <div class="section">
                <h2>⏱️ 最慢用例 Top 10</h2>
                <table>
                    <thead>
                        <tr>
                            <th>排名</th>
                            <th>接口名称</th>
                            <th>用例ID</th>
                            <th>耗时(秒)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for slow in report.slowest_testcases %}
                        <tr>
                            <td>{{ loop.index }}</td>
                            <td>{{ slow.interface_name }}</td>
                            <td><code>{{ slow.testcase_id[:16] }}...</code></td>
                            <td>{{ "%.3f"|format(slow.duration) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
            
            {% if report.error_patterns %}
            <div class="section">
                <h2>🔍 错误模式分析</h2>
                <table>
                    <thead>
                        <tr>
                            <th>错误模式</th>
                            <th>出现次数</th>
                            <th>示例用例</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for pattern in report.error_patterns[:10] %}
                        <tr>
                            <td>{{ pattern.pattern[:80] }}...</td>
                            <td><strong>{{ pattern.count }}</strong></td>
                            <td><code>{{ pattern.example_id[:16] }}...</code></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
            
            <div class="section">
                <h2>📋 测试结果详情</h2>
                {% for result in report.testcase_results %}
                <div class="test-detail">
                    <h4>
                        <span class="status-badge status-{{ result.status }}">
                            {{ result.status.upper() }}
                        </span>
                        {{ result.interface_name }}
                        <small style="color: #999;">({{ result.testcase_id[:16] }}...)</small>
                    </h4>
                    <p><strong>耗时:</strong> {{ "%.3f"|format(result.duration) }}秒</p>
                    {% if result.error_message %}
                    <p><strong>错误:</strong> <span style="color: #f44336;">{{ result.error_message }}</span></p>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div class="footer">
            <p>由 MCP 接口测试智能体应用生成 | Powered by AgentScope</p>
        </div>
    </div>
</body>
</html>
        """
        
        template = Template(template_str)
        html = template.render(report=report)
        
        return html
    
    def _build_progress_bar(self, report: TestReport) -> str:
        """构建 ASCII 进度条"""
        bar_length = 50
        passed_len = int(bar_length * report.passed_count / report.total_count) if report.total_count > 0 else 0
        failed_len = int(bar_length * report.failed_count / report.total_count) if report.total_count > 0 else 0
        error_len = int(bar_length * report.error_count / report.total_count) if report.total_count > 0 else 0
        skipped_len = bar_length - passed_len - failed_len - error_len
        
        bar = (
            "✅" * passed_len +
            "❌" * failed_len +
            "⚠️" * error_len +
            "⏭️" * skipped_len
        )
        
        return f"```\n{bar}\n```"
    
    def _format_test_result(self, result: TestResult, brief: bool = False) -> List[str]:
        """格式化单个测试结果"""
        lines = []
        
        status_emoji = {
            TestCaseStatus.PASSED: "✅",
            TestCaseStatus.FAILED: "❌",
            TestCaseStatus.ERROR: "⚠️",
            TestCaseStatus.SKIPPED: "⏭️",
        }
        
        emoji = status_emoji.get(result.status, "❓")
        
        lines.append(f"#### {emoji} {result.interface_name}")
        lines.append(f"- **用例ID**: `{result.testcase_id}`")
        lines.append(f"- **状态**: {result.status}")
        lines.append(f"- **耗时**: {result.duration:.3f}秒")
        
        if result.error_message:
            lines.append(f"- **错误**: {result.error_message}")
        
        if not brief:
            # 请求详情
            if result.request_log:
                lines.append("")
                lines.append("**请求详情**:")
                lines.append("```json")
                lines.append(json.dumps(result.request_log, indent=2, ensure_ascii=False))
                lines.append("```")
            
            # 响应详情
            if result.response_log:
                lines.append("")
                lines.append("**响应详情**:")
                lines.append("```json")
                lines.append(json.dumps(result.response_log, indent=2, ensure_ascii=False))
                lines.append("```")
            
            # 断言结果
            if result.assertion_results:
                lines.append("")
                lines.append("**断言结果**:")
                for ar in result.assertion_results:
                    status_mark = "✓" if ar.passed else "✗"
                    lines.append(f"- {status_mark} {ar.assertion.type}: {ar.assertion.expected}")
                    if not ar.passed and ar.error_message:
                        lines.append(f"  - 错误: {ar.error_message}")
        
        lines.append("")
        return lines
