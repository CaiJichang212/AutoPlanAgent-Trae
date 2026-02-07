from typing import List, Dict, Any, TypedDict, Annotated, Optional
import operator

class TaskStep(TypedDict):
    id: str
    task: str
    dependencies: List[str]
    status: str  # pending, in_progress, completed, failed
    input: Optional[Any]
    output: Optional[Any]
    tool: Optional[str]

def update_dict(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    return {**existing, **new}

class AgentState(TypedDict):
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
