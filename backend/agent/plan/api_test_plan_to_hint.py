# -*- coding: utf-8 -*-
"""
API 测试专用计划提示词生成器。
针对端到端 API 测试场景优化，引导 Agent 按阶段执行任务并动态管理工具。
"""
from agentscope.plan import Plan

class ApiTestPlanToHint:
    """
    API 测试专用提示生成器，按四阶段引导 Agent：
    1. 文档解析
    2. 用例生成 
    3. 测试执行
    4. 报告生成
    """

    hint_prefix: str = "<system-hint>"
    hint_suffix: str = "</system-hint>"

    no_plan: str = (
        "For API testing requests, you MUST follow the 4-phase workflow:\n"
        "1. **Document Parsing**: Extract API specs from uploaded documents\n"
        "2. **Test Case Generation**: Create comprehensive test cases\n"
        "3. **Test Execution**: Run tests against the target service\n"
        "4. **Report Generation**: Produce actionable insights\n\n"
        "If the user provides an API document or asks for test generation, "
        "create a plan using 'create_plan' with these 4 phases as subtasks.\n\n"
        "# CRITICAL EFFICIENCY RULES\n"
        "- **BE EXTREMELY CONCISE**: Avoid lengthy explanations between tool calls\n"
        "- **ACTION FIRST, WORDS LATER**: Directly call tools instead of explaining what you will do\n"
        "- Use minimal transition text (e.g., 'Applying rules...' instead of full sentences)"
    )

    at_the_beginning: str = (
        "Current API Test Plan:\n"
        "```\n"
        "{plan}\n"
        "```\n"
        "## Starting Phase 1: Document Parsing\n"
        "- First, activate file tools: call `reset_equipped_tools({{\"api_test_tools\": true}})`\n"
        "- Then call `list_uploaded_files(user_id, conversation_id)` to discover files\n"
        "- Finally, use `safe_view_text_file(file_path)` to read the document\n\n"
        "If no files are found, ask the user to upload the API document.\n\n"
        "# CRITICAL EFFICIENCY RULES\n"
        "- **BE EXTREMELY CONCISE**: Avoid lengthy explanations between tool calls\n"
        "- **ACTION FIRST**: Directly call tools, minimize transition text"
    )

    when_a_subtask_in_progress: str = (
        "Current API Test Plan:\n"
        "```\n"
        "{plan}\n"
        "```\n"
        "## Executing: {subtask_name}\n"
        "```\n"
        "{subtask}\n"
        "```\n"
        "### Next Steps:\n"
        "{phase_specific_guidance}\n\n"
        "If stuck, ask the user for clarification or revise the plan."
    )

    when_no_subtask_in_progress: str = (
        "Current API Test Plan:\n"
        "```\n"
        "{plan}\n"
        "```\n"
        "## Completed {index} phases, ready for next phase\n"
        "- Mark the next subtask as 'in_progress' using `update_subtask_state`\n"
        "- Activate required tools for the next phase (see phase guidance below)\n\n"
        "{next_phase_guidance}"
    )

    at_the_end: str = (
        "Current API Test Plan:\n"
        "```\n"
        "{plan}\n"
        "```\n"
        "## All Phases Completed!\n"
        "- Call `finish_plan` with final results\n"
        "- Deactivate all tool groups: `reset_equipped_tools({{\"api_test_tools\": false}})`\n"
        "- Provide a summary including:\n"
        "  • Test coverage stats\n"
        "  • Critical failures\n"
        "  • Actionable recommendations"
    )

    # 阶段特定的引导指令
    PHASE_GUIDANCE = {
        "Document Parsing": (
            "1. Ensure `api_test_tools` is activated\n"
            "2. Use `list_uploaded_files` → `safe_view_text_file` to extract content\n"
            "3. Parse the text into structured API spec (endpoint/method/params)\n"
            "4. Validate spec completeness before proceeding\n"
            "**IMPORTANT**: Minimize text output, focus on actions"
        ),
        "Test Case Generation": (
            "1. Generate positive/negative/security test cases\n"
            "2. Store test cases in a structured format for execution\n"
            "**CRITICAL**: After generating test cases, do NOT output full JSON\n"
            "- Summarize briefly: 'Generated X positive, Y negative, Z security cases'\n"
            "- Do NOT list parameters you will pass\n"
            "- DIRECTLY call the tool, then summarize result"
        ),
        "Test Execution": (
            "1. Ensure target service is running (http://127.0.0.1:5000)\n"
            "2. Execute test cases with `execute_api_test`\n"
            "3. Capture responses, status codes, and performance metrics\n"
            "4. Handle failures gracefully (retry/timeout)"
        ),
        "Report Generation": (
            "1. Analyze test results for pass/fail rates\n"
            "2. Diagnose root causes of failures\n"
            "3. Generate markdown report with:\n"
            "   - Summary table\n"
            "   - Failure details\n"
            "   - Improvement suggestions"
        )
    }

    def __call__(self, plan: Plan | None) -> str | None:
        """Generates phase-aware hints for API testing workflow."""
        if plan is None:
            return f"{self.hint_prefix}{self.no_plan}{self.hint_suffix}"

        # 统计子任务状态
        n_todo, n_in_progress, n_done, n_abandoned = 0, 0, 0, 0
        in_progress_subtask_idx = None
        for idx, subtask in enumerate(plan.subtasks):
            if subtask.state == "todo":
                n_todo += 1
            elif subtask.state == "in_progress":
                n_in_progress += 1
                in_progress_subtask_idx = idx
            elif subtask.state == "done":
                n_done += 1
            elif subtask.state == "abandoned":
                n_abandoned += 1

        # 获取当前阶段名称（假设子任务名包含阶段关键词）
        current_phase = ""
        next_phase_guidance = ""
        
        if n_in_progress > 0 and in_progress_subtask_idx is not None:
            current_phase = plan.subtasks[in_progress_subtask_idx].name
            phase_guidance = self.PHASE_GUIDANCE.get(
                current_phase, 
                "Continue executing the current subtask."
            )
            hint = self.when_a_subtask_in_progress.format(
                plan=plan.to_markdown(),
                subtask_idx=in_progress_subtask_idx,
                subtask_name=current_phase,
                subtask=plan.subtasks[in_progress_subtask_idx].to_markdown(detailed=True),
                phase_specific_guidance=phase_guidance
            )
            
        elif n_in_progress == 0 and n_done == 0:
            # 初始状态
            hint = self.at_the_beginning.format(
                plan=plan.to_markdown(),
            )
            
        elif n_in_progress == 0 and n_done > 0 and (n_done + n_abandoned < len(plan.subtasks)):
            # 准备进入下一阶段
            next_subtask = plan.subtasks[n_done]
            next_phase = next_subtask.name
            next_phase_guidance = self.PHASE_GUIDANCE.get(
                next_phase, 
                "Proceed to the next subtask."
            )
            hint = self.when_no_subtask_in_progress.format(
                plan=plan.to_markdown(),
                index=n_done,
                next_phase_guidance=next_phase_guidance
            )
            
        elif n_done + n_abandoned == len(plan.subtasks):
            # 所有阶段完成
            hint = self.at_the_end.format(
                plan=plan.to_markdown(),
            )
        else:
            hint = self.no_plan

        if hint:
            return f"{self.hint_prefix}{hint}{self.hint_suffix}"
        return None