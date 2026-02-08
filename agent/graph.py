"""代理工作流图定义模块。

该模块使用 langgraph 构建了代理的执行逻辑，包含任务理解、规划、
反馈处理、循环执行和最终报告生成。
"""
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from agent.state import AgentState
from agent.nodes.understanding import understand_task
from agent.nodes.planning import plan_task
from agent.nodes.execution import execute_step
from agent.nodes.feedback import handle_feedback
from agent.nodes.reporting import generate_report
from agent.utils import setup_logger

logger = setup_logger("agent_graph")

def should_continue_execution(state: AgentState):
    """判断是否继续执行步骤或结束。

    检查当前执行的步骤索引和错误数量，决定下一步是继续执行、生成报告还是结束。

    Args:
        state: 当前的代理状态。

    Returns:
        字符串标识，指示下一个节点（"execute", "report", "end"）。
    """
    # 即使有错误，也尝试继续执行，让 LLM 在下一步尝试自修复或报告错误
    # 除非错误数量过多，防止无限循环（虽然这里是线性执行，但以防万一）
    if len(state.get("errors", [])) > 3:
        logger.error(f"错误过多，停止执行: {state['errors']}")
        return "end"
    
    if state["current_step_index"] < len(state["plan"]):
        return "execute"
    else:
        logger.info("所有计划步骤已完成，准备生成报告。")
        return "report"

def create_graph():
    """创建并编译代理的工作流图。

    定义节点、边以及条件逻辑，并启用内存检查点支持中断恢复。

    Returns:
        编译后的 CompiledGraph 对象。
    """
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("understand", understand_task)
    workflow.add_node("plan", plan_task)
    workflow.add_node("handle_feedback", handle_feedback)
    workflow.add_node("execute", execute_step)
    workflow.add_node("report", generate_report)

    # 构建边
    workflow.add_edge(START, "understand")
    workflow.add_edge("understand", "plan")
    workflow.add_edge("plan", "handle_feedback")
    
    # handle_feedback 节点之后的分支逻辑
    workflow.add_conditional_edges(
        "handle_feedback",
        lambda x: "plan" if not x["is_approved"] else "execute",
        {
            "plan": "plan",
            "execute": "execute"
        }
    )

    workflow.add_conditional_edges(
        "execute",
        should_continue_execution,
        {
            "execute": "execute",
            "report": "report",
            "end": END
        }
    )
    
    workflow.add_edge("report", END)

    # 设置 Checkpointer 支持中断恢复
    memory = MemorySaver()
    
    return workflow.compile(checkpointer=memory, interrupt_before=["handle_feedback"])

graph = create_graph()
