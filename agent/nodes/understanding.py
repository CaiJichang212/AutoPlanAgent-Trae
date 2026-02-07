from typing import Dict, Any
from pydantic import BaseModel, Field
from agent.state import AgentState
from agent.utils import get_model_from_name, setup_logger, load_prompt

logger = setup_logger("understand_node")

class TaskUnderstanding(BaseModel):
    goal: str = Field(description="分析目标")
    data_scope: str = Field(description="数据范围")
    time_dimension: str = Field(description="时间维度")
    business_context: str = Field(description="业务背景")
    key_metrics: list[str] = Field(description="关键分析指标")
    constraints: list[str] = Field(description="分析约束或特殊要求")

def understand_task(state: AgentState) -> Dict[str, Any]:
    """任务理解与解析模块"""
    logger.info(f"开始理解任务: {state.get('input', '')[:50]}...")
    llm = get_model_from_name()
    structured_llm = llm.with_structured_output(TaskUnderstanding)
    
    prompt_template = load_prompt("understanding")
    prompt = prompt_template.format(input=state['input'])
    
    understanding = structured_llm.invoke(prompt)
    
    return {
        "understanding": understanding.model_dump(),
        "context": {},
        "plan": [],
        "current_step_index": 0,
        "is_approved": False,
        "awaiting_approval": False,
        "errors": [],
        "history": [{"role": "assistant", "content": f"任务理解完成：{understanding.goal}"}]
    }
