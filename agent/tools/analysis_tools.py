from langchain_experimental.utilities import PythonREPL
from langchain_core.tools import tool
import pandas as pd
import numpy as np

import json
import io
import sys

# 初始化一个全局共享的 REPL 环境，确保 globals 和 locals 是同一个字典，
# 从而避免 exec() 中 list comprehension/generator expression 的作用域问题。
# 提前注入常用的库，确保在 lambda 或列表推导式中也能访问
import scipy
import sklearn
import statsmodels.api as sm

shared_scope = {
    'pd': pd,
    'np': np,
    'sys': sys,
    'json': json,
    'io': io,
    'plt': None,
    'sns': None,
    'scipy': scipy,
    'sklearn': sklearn,
    'sm': sm
}
# 移除 repl = PythonREPL(...)，改为直接使用 exec

@tool
def python_analysis(code: str) -> str:
    """
    执行 Python 代码进行数据分析、挖掘或统计建模。
    代码应包含必要的 import 语句（如 pandas, numpy, scipy, sklearn 等）。
    变量 context 可以在代码中访问，用于获取之前步骤的结果。
    注意：
    - 如果数据量过小无法进行高级建模（如 ARIMA），请退而求其次使用简单的统计描述或线性趋势。
    - 务必处理空数据或异常值情况。
    最后的结果请通过 print() 输出结论摘要。
    """
    try:
        output_buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output_buffer
        try:
            # 使用同一个字典作为 globals 和 locals，确保 lambda/listcomp 的作用域正确
            exec(code, shared_scope, shared_scope)
        finally:
            sys.stdout = old_stdout
        
        result = output_buffer.getvalue()
        return result if result else "代码执行成功（无输出）"
    except SystemExit:
        # SystemExit 通常是由 exit() 或 quit() 触发的，不视作错误
        sys.stdout = sys.__stdout__ # 确保恢复 stdout
        return output_buffer.getvalue() or "代码执行成功 (SystemExit)"
    except Exception as e:
        import traceback
        if 'old_stdout' in locals():
            sys.stdout = old_stdout
        error_info = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
        return json.dumps(error_info, ensure_ascii=False)
