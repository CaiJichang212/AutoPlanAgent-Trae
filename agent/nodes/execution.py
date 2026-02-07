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

def extract_first_json(text: str):
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
            # 预解析 context 中的 JSON 字符串，使 LLM 在 Python 中可以直接使用 dict/list
            parsed_context = {}
            for k, v in state['context'].items():
                try:
                    # 如果是 JSON 字符串则解析，否则保持原样
                    if isinstance(v, str) and (v.startswith('{') or v.startswith('[')):
                        parsed_context[k] = json.loads(v)
                    else:
                        parsed_context[k] = v
                except:
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

            context_json = json.dumps(normalized_context, ensure_ascii=False)
            indented_code = "\n".join(f"    {line}" for line in code.splitlines())
            if not indented_code.strip():
                indented_code = "    pass"
            full_code = f"""
import json
import pandas as pd
import numpy as np
import io

# 注入上下文数据 (已预解析)
context_str = {repr(context_json)}
context = json.loads(context_str)

def exit(*args, **kwargs):
    raise SystemExit(*args)

def quit(*args, **kwargs):
    raise SystemExit(*args)

try:
{indented_code}
except SystemExit as e:
    print(json.dumps({{"warning": "Execution halted by exit()", "detail": str(e)}}, ensure_ascii=False, default=str))
"""
            result = python_analysis.invoke(full_code)
        elif current_step['tool'] == 'visualizer':
            viz_json = extract_code(response, "json")
            try:
                # 尝试预处理 JSON 字符串，移除可能的末尾非 JSON 内容（如注释）
                clean_json = re.sub(r'//.*$', '', viz_json, flags=re.MULTILINE)
                viz_data = json.loads(clean_json, strict=False)
                # 在 plot_code 中注入 context (同样进行预解析)
                parsed_context = {}
                for k, v in state['context'].items():
                    try:
                        if isinstance(v, str) and (v.startswith('{') or v.startswith('[')):
                            parsed_context[k] = json.loads(v)
                        else:
                            parsed_context[k] = v
                    except:
                        parsed_context[k] = v
                
                context_json = json.dumps(parsed_context, ensure_ascii=False)
                if isinstance(viz_data, dict):
                    embedded = viz_data.get('plot_code')
                    if isinstance(embedded, str):
                        viz_data['plot_code'] = f"""
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

context_str = {repr(context_json)}
context = json.loads(context_str)

{embedded}
"""
                    elif isinstance(embedded, dict):
                        candidate = embedded.get('plot_code') or embedded.get('code') or ""
                        viz_data['plot_code'] = f"""
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

context_str = {repr(context_json)}
context = json.loads(context_str)

{candidate}
"""
                    else:
                        inner = extract_first_json(str(embedded))
                        code_str = ""
                        if isinstance(inner, dict):
                            code_str = inner.get('plot_code') or inner.get('code') or ""
                        viz_data['plot_code'] = f"""
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

context_str = {repr(context_json)}
context = json.loads(context_str)

{code_str}
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

    if current_step['tool'] in ('python_analysis', 'visualizer') and isinstance(result, str):
        extracted = extract_first_json(result)
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
    
    # 更新步骤状态和结果
    current_step['output'] = result
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
