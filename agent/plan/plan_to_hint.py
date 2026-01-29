# -*- coding: utf-8 -*-
"""
自定义计划提示词生成器。
将 AgentScope 的默认提示词翻译为中文，并针对 MCP 自动化测试场景进行优化。
"""
from agentscope.plan import Plan

class CustomPlanToHint:
    """
    自定义函数，根据当前计划生成提示信息，引导智能体执行下一步。
    """

    hint_prefix: str = "<system-hint>"
    hint_suffix: str = "</system-hint>"

    no_plan: str = (
        "If the user's request is complex (e.g., building a website, game, or application, or executing a series of intricate automated test steps), "
        "or if it requires multiple steps to complete (e.g., researching a topic from multiple sources, or performing an end-to-end API testing workflow), "
        "you must first create a plan by calling 'create_plan'. Otherwise, you can directly execute the user's query without planning."
    )

    at_the_beginning: str = (
        "Current Plan:\n"
        "```\n"
        "{plan}\n"
        "```\n"
        "Your options include:\n"
        "- Call 'update_subtask_state' with subtask_idx=0 and state='in_progress' to mark the first subtask as 'in progress', then begin executing it.\n"
        "- If the first subtask cannot be executed immediately, analyze the reason and determine what actions you can take to advance the plan—such as asking the user for more information or calling 'revise_current_plan' to modify the plan.\n"
        "- If the user asks you to do something unrelated to the current plan, prioritize fulfilling the user's request before returning to the plan.\n"
        "- If the user no longer wishes to proceed with the current plan, confirm with the user and call 'finish_plan'.\n"
    )

    when_a_subtask_in_progress: str = (
        "Current Plan:\n"
        "```\n"
        "{plan}\n"
        "```\n"
        "The subtask at index {subtask_idx}, '{subtask_name}', is currently 'in progress'. Its details are as follows:\n"
        "```\n"
        "{subtask}\n"
        "```\n"
        "Your options include:\n"
        "- Continue executing this subtask and obtain its result.\n"
        "- If the subtask is complete, call 'finish_subtask' and provide the specific outcome.\n"
        "- If needed, ask the user for additional information.\n"
        "- If necessary, revise the plan by calling 'revise_current_plan'.\n"
        "- If the user requests something unrelated to the plan, prioritize the user's query before returning to the plan."
    )

    when_no_subtask_in_progress: str = (
        "Current Plan:\n"
        "```\n"
        "{plan}\n"
        "```\n"
        "The first {index} subtasks have been completed, and there is currently no subtask marked as 'in progress'. Your options include:\n"
        "- Call 'update_subtask_state' to mark the next subtask as 'in progress' and begin executing it.\n"
        "- If needed, ask the user for additional information.\n"
        "- If necessary, revise the plan by calling 'revise_current_plan'.\n"
        "- If the user requests something unrelated to the plan, prioritize the user's query before returning to the plan.\n"
        "- Call 'reset_equipped_tools' to disable all non-essential tool groups if needed."
    )

    at_the_end: str = (
        "Current Plan:\n"
        "```\n"
        "{plan}\n"
        "```\n"
        "All subtasks have been completed. Your options include:\n"
        "- Call 'finish_plan' with the final execution results, summarize the entire process and outcomes for the user, and conclude the plan.\n"
        "- If necessary, revise the plan by calling 'revise_current_plan'.\n"
        "- If the user requests something unrelated to the plan, prioritize the user's query before returning to the plan."
    )

    def __call__(self, plan: Plan | None) -> str | None:
        """Generates a hint message based on the input plan to guide the agent's next action."""
        if plan is None:
            hint = self.no_plan

        else:
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

            hint = None
            if n_in_progress == 0 and n_done == 0:
                # 所有子任务都是待办状态
                hint = self.at_the_beginning.format(
                    plan=plan.to_markdown(),
                )
            elif n_in_progress > 0 and in_progress_subtask_idx is not None:
                # 有一个子任务正在进行中
                hint = self.when_a_subtask_in_progress.format(
                    plan=plan.to_markdown(),
                    subtask_idx=in_progress_subtask_idx,
                    subtask_name=plan.subtasks[in_progress_subtask_idx].name,
                    subtask=plan.subtasks[in_progress_subtask_idx].to_markdown(
                        detailed=True,
                    ),
                )
            elif n_in_progress == 0 and n_done > 0 and (n_done + n_abandoned < len(plan.subtasks)):
                # 没有正在进行的子任务，但有些已经完成，且还有待办任务
                hint = self.when_no_subtask_in_progress.format(
                    plan=plan.to_markdown(),
                    index=n_done,
                )
            elif n_done + n_abandoned == len(plan.subtasks):
                # 所有子任务都已完成或废弃
                hint = self.at_the_end.format(
                    plan=plan.to_markdown(),
                )

        if hint:
            return f"{self.hint_prefix}{hint}{self.hint_suffix}"

        return hint
