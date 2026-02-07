from typing import List, Dict, Any
from pydantic import BaseModel, Field
from agent.state import AgentState, TaskStep
from agent.utils import get_model_from_name, setup_logger, load_prompt

logger = setup_logger("planning_node")

class Plan(BaseModel):
    steps: List[TaskStep] = Field(description="任务拆解后的执行步骤序列")

def plan_task(state: AgentState) -> Dict[str, Any]:
    """任务拆解与规划引擎"""
    understanding = state['understanding']
    logger.info(f"开始规划任务: {understanding['goal']}")
    llm = get_model_from_name()
    structured_llm = llm.with_structured_output(Plan)
    
    prompt_template = load_prompt("planning")
    prompt = prompt_template.format(
        goal=understanding['goal'],
        data_scope=understanding['data_scope'],
        key_metrics=', '.join(understanding['key_metrics']),
        business_context=understanding['business_context']
    )
    
    plan_output = structured_llm.invoke(prompt)
    
    # 初始化步骤状态
    for step in plan_output.steps:
        step['status'] = 'pending'
    
    return {
        "plan": plan_output.steps,
        "current_step_index": 0,
        "awaiting_approval": True,  # 规划完成后进入待确认状态
        "history": [{"role": "assistant", "content": "任务规划完成，请确认执行计划。"}]
    }
