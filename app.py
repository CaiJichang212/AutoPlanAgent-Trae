"""自主数据分析智能体 API 服务。

该模块使用 FastAPI 提供了一个 RESTful 接口，允许用户启动数据分析任务、
提供反馈、并查询任务状态。它通过 LangGraph 管理智能体的状态流转。
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
from agent.graph import graph
from agent.state import AgentState
import logging
from agent.utils import setup_logger

app = FastAPI(title="Autonomous Data Analysis Agent API")
logger = setup_logger("agent_api", "logs/api.log")

# 内存中存储线程 ID
threads = {}

class TaskRequest(BaseModel):
    """启动任务的请求模型。

    Attributes:
        query: 用户输入的分析需求。
    """
    query: str

class FeedbackRequest(BaseModel):
    """用户反馈的请求模型。

    Attributes:
        thread_id: 任务的唯一标识符。
        feedback: 用户的反馈内容。
    """
    thread_id: str
    feedback: str

@app.post("/tasks/start")
async def start_task(request: TaskRequest):
    """启动一个新的分析任务。

    Args:
        request: 包含用户查询的 TaskRequest 对象。

    Returns:
        包含 thread_id、当前状态、任务理解和初步计划的字典。

    Raises:
        HTTPException: 如果启动任务过程中发生错误。
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # 初始化状态
    initial_state = {
        "input": request.query,
        "understanding": {},
        "plan": [],
        "current_step_index": 0,
        "context": {},
        "history": [],
        "errors": [],
        "awaiting_approval": False,
        "is_approved": False
    }
    
    # 运行图直到遇到 interrupt (handle_feedback 之前)
    try:
        events = []
        for event in graph.stream(initial_state, config):
            events.append(event)
            logger.info(f"Thread {thread_id} Event: {list(event.keys())[0]}")
        
        state = graph.get_state(config).values
        return {
            "thread_id": thread_id,
            "status": "awaiting_approval",
            "understanding": state.get("understanding"),
            "plan": state.get("plan")
        }
    except Exception as e:
        logger.error(f"Error starting task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks/feedback")
async def provide_feedback(request: FeedbackRequest):
    """为正在运行的任务提供用户反馈。

    Args:
        request: 包含 thread_id 和 feedback 的 FeedbackRequest 对象。

    Returns:
        包含任务最新状态或最终报告的字典。

    Raises:
        HTTPException: 如果任务未找到或处理反馈时发生错误。
    """
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # 获取当前状态
    current_state = graph.get_state(config)
    if not current_state.values:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 更新历史记录（作为用户输入）
    graph.update_state(config, {"history": [{"role": "user", "content": request.feedback}]})
    
    # 继续运行
    try:
        for event in graph.stream(None, config):
            logger.info(f"Thread {request.thread_id} Resumed Event: {list(event.keys())[0]}")
        
        final_state = graph.get_state(config).values
        
        if final_state.get("report"):
            return {
                "status": "completed",
                "report": final_state.get("report")
            }
        else:
            return {
                "status": "in_progress",
                "current_step": final_state.get("current_step_index"),
                "plan": final_state.get("plan")
            }
            
    except Exception as e:
        logger.error(f"Error in feedback processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/{thread_id}/status")
async def get_status(thread_id: str):
    """获取指定任务的完整状态。

    Args:
        thread_id: 任务的唯一标识符。

    Returns:
        任务的当前状态值。

    Raises:
        HTTPException: 如果任务未找到。
    """
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config).values
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return state

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
