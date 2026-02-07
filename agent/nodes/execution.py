from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage
from agent.state import AgentState, TaskStep
from agent.tools.db_tools import sql_query, get_db_schema
from agent.tools.analysis_tools import python_analysis
from agent.tools.viz_tools import visualizer
from agent.utils import get_model_from_name, setup_logger, load_prompt
import json

import re

logger = setup_logger("execution_node")

def extract_code(text: str, lang: str) -> str:
    """从文本中提取指定语言的代码块"""
    pattern = f"```{lang}\n?(.*?)\n?```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 如果没有 markdown 标记，尝试清理常见的提示语并返回全文
    return text.strip().replace("```", "")

def execute_step(state: AgentState) -> Dict[str, Any]:
    """动态执行当前计划中的步骤"""
    plan = state['plan']
    idx = state['current_step_index']
    
    if idx >= len(plan):
        return {"awaiting_approval": False}

    current_step = plan[idx]
    logger.info(f"执行步骤 {idx+1}/{len(plan)}: {current_step['task']} (工具: {current_step['tool']})")
    current_step['status'] = 'in_progress'
    
    # 准备执行环境
    llm = get_model_from_name()
    
    # 获取数据库 Schema 信息供 SQL 编写参考
    db_schema = ""
    if current_step['tool'] == 'sql_query':
        db_schema = get_db_schema.invoke({})

    # 裁剪上下文，防止 token 溢出
    # 只保留最近的 3 个步骤结果，且限制每个结果的字符数
    truncated_context = {}
    context_keys = list(state['context'].keys())
    relevant_keys = context_keys[-3:] # 获取最后3个
    
    for k in relevant_keys:
        val = str(state['context'][k])
        if len(val) > 5000:
            truncated_context[k] = val[:5000] + "...(此处仅为提示词中的截断，实际 Python 执行环境中的 context 变量包含完整数据)"
        else:
            truncated_context[k] = val
            
    context_summary = json.dumps(truncated_context, indent=2, ensure_ascii=False)
    
    prompt_template = load_prompt("execution")
    prompt = prompt_template.replace("{task}", current_step['task']) \
                            .replace("{tool}", current_step['tool']) \
                            .replace("{context_summary}", context_summary) \
                            .replace("{db_schema}", db_schema)
    
    response = llm.invoke(prompt).content
    logger.info(f"LLM 响应: {response}")
    
    # 执行工具
    result = ""
    try:
        if current_step['tool'] == 'sql_query':
            sql = extract_code(response, "sql")
            result = sql_query.invoke(sql)
        elif current_step['tool'] == 'python_analysis':
            code = extract_code(response, "python")
            # 使用 json.dumps 注入 context，并在代码中解析，比 repr 更稳健
            context_json = json.dumps(state['context'], ensure_ascii=False)
            full_code = f"""
import json
import pandas as pd
import numpy as np
import io

# 注入上下文数据
context_str = {repr(context_json)}
context = json.loads(context_str)

{code}
"""
            result = python_analysis.invoke(full_code)
        elif current_step['tool'] == 'visualizer':
            viz_json = extract_code(response, "json")
            try:
                # 尝试预处理 JSON 字符串，移除可能的末尾非 JSON 内容（如注释）
                clean_json = re.sub(r'//.*$', '', viz_json, flags=re.MULTILINE)
                viz_data = json.loads(clean_json, strict=False)
                # 在 plot_code 中注入 context
                if 'plot_code' in viz_data:
                    context_json = json.dumps(state['context'], ensure_ascii=False)
                    viz_data['plot_code'] = f"""
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

context_str = {repr(context_json)}
context = json.loads(context_str)

{viz_data['plot_code']}
"""
                result = visualizer.invoke(viz_data)
            except Exception as e:
                result = f"无法解析绘图参数: {str(e)}\n原内容: {viz_json}"
        else:
            raise ValueError(f"未知的工具: {current_step['tool']}")
    except Exception as e:
        error_msg = f"执行出错: {str(e)}"
        logger.error(error_msg)
        current_step['status'] = 'failed'
        current_step['output'] = error_msg
        return {"errors": [error_msg], "plan": plan}

    # 更新步骤状态和结果
    current_step['output'] = result
    current_step['status'] = 'completed'
    plan[idx] = current_step
    
    # 更新全局上下文
    new_context = {current_step['id']: result}
    
    return {
        "plan": plan,
        "current_step_index": idx + 1,
        "context": new_context,
        "history": [{"role": "assistant", "content": f"步骤【{current_step['task']}】执行完成。"}]
    }
