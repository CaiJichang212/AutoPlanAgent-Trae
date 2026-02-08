"""状态定义模块，定义了代理在执行过程中维护的状态结构。

该模块使用 TypedDict 定义了任务步骤和全局状态，并提供了状态更新的辅助函数。
"""
from typing import List, Dict, Any, TypedDict, Annotated, Optional
import operator

class TaskStep(TypedDict):
    """任务步骤结构。

    Attributes:
        id: 步骤的唯一标识。
        task: 任务描述。
        dependencies: 依赖的步骤 ID 列表。
        status: 当前状态（pending, in_progress, completed, failed）。
        input: 步骤的输入参数。
        output: 步骤的执行结果。
        tool: 使用的工具名称。
    """
    id: str
    task: str
    dependencies: List[str]
    status: str  # pending, in_progress, completed, failed
    input: Optional[Any]
    output: Optional[Any]
    tool: Optional[str]

def update_dict(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """合并两个字典，用于状态更新。

    Args:
        existing: 原始字典。
        new: 要合并的新字典。

    Returns:
        合并后的新字典。
    """
    return {**existing, **new}

class AgentState(TypedDict):
    """代理的全局状态结构。

    Attributes:
        input: 用户的原始输入请求。
        understanding: 对任务的结构化理解。
        plan: 拆解后的任务执行计划。
        current_step_index: 当前正在执行或准备执行的步骤索引。
        context: 存储所有步骤的中间结果和累积数据。
        history: 对话历史记录，用于跟踪与用户的交互。
        report: 最终生成的分析报告。
        errors: 执行过程中产生的错误信息列表。
        awaiting_approval: 标记当前是否在等待用户审批。
        is_approved: 标记用户是否已批准当前计划或操作。
    """
    # 用户输入
    input: str
    
    # 任务理解报告
    understanding: Dict[str, Any]
    
    # 执行计划
    plan: List[TaskStep]
    
    # 当前执行到的步骤索引
    current_step_index: int
    
    # 累积的中间结果和数据上下文
    context: Annotated[Dict[str, Any], update_dict]
    
    # 用户反馈/对话历史
    history: Annotated[List[Dict[str, str]], operator.add]
    
    # 最终报告
    report: Optional[str]
    
    # 错误信息
    errors: Annotated[List[str], operator.add]
    
    # 是否需要用户确认
    awaiting_approval: bool
    
    # 用户是否已确认
    is_approved: bool
