"""执行节点，负责根据计划执行具体的任务步骤。

该模块包含执行任务、提取代码块、解析 JSON 以及规范化上下文等功能。
"""
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

# 用于在执行 python_analysis 时临时存储上下文数据
_current_context = None

def extract_code(text: str, lang: str) -> str:
    """从文本中提取指定语言的代码块。

    Args:
        text: 包含代码块的原始文本。
        lang: 指定的代码语言（如 'python', 'sql', 'json'）。

    Returns:
        提取出的代码字符串。如果没有匹配到，则尝试返回通用代码块或清理后的文本。
    """
    # 优先匹配指定语言的代码块
    pattern = f"```{lang}\n?(.*?)\n?```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 尝试匹配通用的代码块
    pattern_generic = r"```\n?(.*?)\n?```"
    match_generic = re.search(pattern_generic, text, re.DOTALL)
    if match_generic:
        return match_generic.group(1).strip()
        
    # 如果没有 markdown 标记，尝试清理常见的提示语并返回全文
    # 移除首尾可能存在的反引号
    return text.strip().strip('`').strip()

def extract_first_json(text: str):
    """从文本中提取第一个有效的 JSON 对象或数组。

    Args:
        text: 包含 JSON 的文本。

    Returns:
        解析后的 JSON 对象（字典或列表），如果未找到则返回 None。
    """
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            return json.loads(stripped)
        except Exception:
            pass
    start = None
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}":
            if start is not None:
                depth -= 1
                if depth == 0:
                    candidate = text[start:i+1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        start = None
                        continue
    return None

def extract_last_json(text: str):
    """从文本中提取最后一个有效的 JSON 对象或数组。

    通常用于处理 LLM 在输出代码或结果后又添加了额外说明的情况。

    Args:
        text: 包含 JSON 的文本。

    Returns:
        解析后的 JSON 对象，优先返回包含特定键（如 'data', 'result'）的对象。
    """
    if not isinstance(text, str):
        return None
    
    # 查找所有可能是 JSON 对象或数组的部分
    # 使用递归下降的思想或简单的堆栈匹配来找到完整的 JSON 结构
    results = []
    
    # 查找所有 { 和 [
    for i in range(len(text)):
        if text[i] in ('{', '['):
            start = i
            target = '}' if text[i] == '{' else ']'
            depth = 0
            for j in range(i, len(text)):
                if text[j] == text[i]:
                    depth += 1
                elif text[j] == target:
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:j+1]
                        try:
                            val = json.loads(candidate)
                            # 如果是字典且包含数据或结果，或者是列表且不为空，则认为是有效的
                            results.append(val)
                            break
                        except Exception:
                            pass
    
    if not results:
        return None
        
    # 优先返回包含 'data' 或 'cleaned_data' 或 'result' 的最后一个对象
    for res in reversed(results):
        if isinstance(res, dict):
            if any(k in res for k in ('data', 'cleaned_data', 'result', 'rankings', 'composite_score')):
                return res
                
    # 否则返回最后一个
    return results[-1]

def get_normalized_context(raw_context: Dict[str, Any]) -> Dict[str, Any]:
    """预解析 context 中的 JSON 字符串，并进行字段别名规范化。

    Args:
        raw_context: 原始上下文字典，值可能是字符串形式的 JSON。

    Returns:
        规范化后的上下文字典，其中特定的财务字段会被映射到统一的别名。
    """
    parsed_context = {}
    for k, v in raw_context.items():
        try:
            # 先尝试直接解析
            if isinstance(v, str):
                v_clean = v.strip()
                if (v_clean.startswith('{') and v_clean.endswith('}')) or \
                   (v_clean.startswith('[') and v_clean.endswith(']')):
                    parsed_context[k] = json.loads(v_clean)
                else:
                    # 尝试使用 extract_last_json 提取
                    extracted = extract_last_json(v)
                    if extracted is not None:
                        parsed_context[k] = extracted
                    else:
                        parsed_context[k] = v
            else:
                parsed_context[k] = v
        except Exception:
            parsed_context[k] = v

    rename_map = {
        "revenue_billion": "revenue",
        "net_profit_billion": "net_profit",
        "gross_margin_pct": "gross_margin",
        "revenue_growth_pct": "revenue_growth",
        "net_profit_growth_pct": "net_profit_growth",
        "on_hand_orders_billion": "on_hand_orders",
        "update_date": "report_date"
    }
    normalized_context = {}
    for k, v in parsed_context.items():
        if isinstance(v, list) and all(isinstance(item, dict) for item in v):
            remapped = []
            for item in v:
                row = {}
                for key, val in item.items():
                    alias = rename_map.get(key, key)
                    row[key] = val
                    row[alias] = val
                remapped.append(row)
            normalized_context[k] = remapped
        elif isinstance(v, dict) and isinstance(v.get("data"), list):
            remapped = []
            for item in v["data"]:
                if isinstance(item, dict):
                    row = {}
                    for key, val in item.items():
                        alias = rename_map.get(key, key)
                        row[key] = val
                        row[alias] = val
                    remapped.append(row)
                else:
                    remapped.append(item)
            new_dict = dict(v)
            new_dict["data"] = remapped
            normalized_context[k] = new_dict
        else:
            normalized_context[k] = v
    return normalized_context

def execute_step(state: AgentState) -> Dict[str, Any]:
    """动态执行当前计划中的步骤。

    根据 state 中的 current_step_index 获取当前步骤，调用 LLM 生成执行代码/指令，
    并调用相应的工具（SQL, Python, Visualizer）获取结果。

    Args:
        state: 当前的代理状态。

    Returns:
        包含更新后的 plan、current_step_index、context 和 history 的字典。
    """
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
    # 只保留最近的 3 个步骤结果，且对列表数据进行智能截断
    truncated_context = {}
    context_keys = list(state['context'].keys())
    relevant_keys = context_keys[-3:] # 获取最后3个
    
    for k in relevant_keys:
        val = state['context'][k]
        if isinstance(val, list) and len(val) > 20:
            # 如果是列表且长度超过 20，保留前 10 和后 10 条
            truncated_val = val[:10] + [{"...": f"已截断 {len(val)-20} 条数据，仅显示头部和尾部各 10 条以供参考"}] + val[-10:]
            truncated_context[k] = truncated_val
        elif isinstance(val, str) and len(val) > 5000:
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
    is_direct_json = False
    try:
        if current_step['tool'] == 'sql_query':
            sql = extract_code(response, "sql")
            result = sql_query.invoke(sql)
        elif current_step['tool'] == 'python_analysis':
            code = extract_code(response, "python")

            if not code or code == "":
                logger.error("LLM 返回了空的 Python 代码块")
                current_step['status'] = 'failed'
                current_step['output'] = "错误：模型生成的 Python 代码为空。"
                return {"plan": plan, "errors": [current_step['output']]}

            # 鲁棒性增强：如果提取的代码看起来像 JSON 而不是 Python 代码，
            # 说明 LLM 可能直接输出了错误信息 JSON，而不是生成代码。
            if code.strip().startswith("{") and code.strip().endswith("}"):
                try:
                    json_res = json.loads(code)
                    if "error" in json_res:
                        result = code
                        is_direct_json = True
                except Exception:
                    pass

            if not is_direct_json:
                normalized_context = get_normalized_context(state["context"])
                
                # 构建完整的 Python 代码，包含必要的 import
                code_template = """
import json
import pandas as pd
import numpy as np
import io
import sys
from agent.tools.analysis_tools import shared_scope

# 注入常用的库到共享作用域
shared_scope['pd'] = pd
shared_scope['np'] = np
shared_scope['sys'] = sys
shared_scope['json'] = json
shared_scope['io'] = io

# 直接注入上下文数据
import agent.nodes.execution as exec_mod
shared_scope['context'] = exec_mod._current_context

def exit(*args, **kwargs):
    sys.exit(*args)

def quit(*args, **kwargs):
    sys.exit(*args)

# 将 exit/quit 也注入共享作用域
shared_scope['exit'] = exit
shared_scope['quit'] = quit

# 执行用户代码
{user_code}
"""
                full_code = code_template.replace("{user_code}", code)
                # 使用全局变量临时存储 context，以便在 exec 中访问
                global _current_context
                _current_context = normalized_context
                
                logger.debug(f"即将执行的 Python 代码:\n{full_code}")
                result = python_analysis.invoke(full_code)
                # 清理
                _current_context = None
        elif current_step['tool'] == 'visualizer':
            viz_json = extract_code(response, "json")
            try:
                # 尝试预处理 JSON 字符串，移除可能的末尾非 JSON 内容
                clean_json = re.sub(r'//.*$', '', viz_json, flags=re.MULTILINE)
                viz_data = json.loads(clean_json, strict=False)
                
                # 如果 viz_data 不是字典，尝试提取最后一个 JSON
                if not isinstance(viz_data, dict):
                    viz_data = extract_last_json(viz_json) or {"plot_code": viz_json, "filename": "plot.png"}

                # 提取 plot_code 和 filename
                plot_code = viz_data.get('plot_code') or viz_data.get('code') or ""
                filename = viz_data.get('filename') or "plot.png"
                
                # 如果 plot_code 还是空的，尝试从嵌套的 viz_data 中提取
                if not plot_code and isinstance(viz_data.get('viz_data'), dict):
                    inner = viz_data.get('viz_data')
                    plot_code = inner.get('plot_code') or inner.get('code') or ""

                # 准备调用工具的参数
                tool_input = {
                    "plot_code": plot_code,
                    "filename": filename,
                    "context": get_normalized_context(state["context"])
                }
                result = visualizer.invoke(tool_input)
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

    if current_step['tool'] in ('python_analysis', 'visualizer') and isinstance(result, str):
        extracted = extract_last_json(result)
        if extracted is not None:
            result = json.dumps(extracted, ensure_ascii=False, default=str)
    
    # 结果规范化：将非 JSON 的错误字符串包装为 JSON，便于后续步骤处理
    if isinstance(result, str):
        is_json_like = result.strip().startswith("{") or result.strip().startswith("[")
        if not is_json_like and current_step['tool'] in ('python_analysis', 'visualizer'):
            safe = {"error": result, "data": []}
            try:
                result = json.dumps(safe, ensure_ascii=False, default=str)
            except Exception:
                result = str(safe)
    
    # 检查结果中是否包含错误
    has_error = False
    error_detail = ""
    try:
        if isinstance(result, str):
            res_obj = json.loads(result)
        else:
            res_obj = result
            
        if isinstance(res_obj, dict) and "error" in res_obj:
            has_error = True
            error_detail = res_obj["error"]
        elif isinstance(res_obj, list) and len(res_obj) > 0 and isinstance(res_obj[0], dict) and "error" in res_obj[0]:
            has_error = True
            error_detail = res_obj[0]["error"]
    except Exception:
        pass

    # 更新步骤状态和结果
    current_step['output'] = result
    if has_error:
        logger.error(f"步骤执行失败: {error_detail}")
        current_step['status'] = 'failed'
        # 如果是关键步骤失败，可以考虑在这里中断或记录错误
        return {
            "plan": plan,
            "errors": [f"Step {current_step['id']} failed: {error_detail}"],
            "history": [{"role": "assistant", "content": f"步骤【{current_step['task']}】执行失败: {error_detail}"}]
        }
    
    current_step['status'] = 'completed'
    plan[idx] = current_step
    
    # 更新全局上下文
    new_context = {**state['context'], current_step['id']: result}
    
    return {
        "plan": plan,
        "current_step_index": idx + 1,
        "context": new_context,
        "history": [{"role": "assistant", "content": f"步骤【{current_step['task']}】执行完成。"}]
    }
