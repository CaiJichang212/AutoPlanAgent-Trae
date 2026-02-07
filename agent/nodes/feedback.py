from typing import Dict, Any
from agent.state import AgentState
from agent.utils import setup_logger

logger = setup_logger("feedback_node")

def handle_feedback(state: AgentState) -> Dict[str, Any]:
    """处理用户反馈"""
    last_message = state['history'][-1]['content'] if state['history'] else ""
    logger.info(f"收到用户反馈: {last_message}")
    
    # 简单的关键词判断逻辑，实际应用中可用 LLM 判断意图
    if any(word in last_message for word in ["同意", "执行", "开始", "确认", "ok", "yes", "proceed"]):
        return {
            "is_approved": True,
            "awaiting_approval": False,
            "history": [{"role": "assistant", "content": "好的，开始执行分析计划。"}]
        }
    else:
        # 认为用户有修改意见，需要重新规划
        return {
            "is_approved": False,
            "awaiting_approval": False,
            "plan": [], # 清空计划触发重新规划
            "history": [{"role": "assistant", "content": f"收到您的反馈：'{last_message}'。我将根据您的要求调整计划。"}]
        }
