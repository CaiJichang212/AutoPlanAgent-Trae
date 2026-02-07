from langchain_experimental.utilities import PythonREPL
from langchain_core.tools import tool
import pandas as pd
import numpy as np

repl = PythonREPL()

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
        # 在执行前可以注入一些上下文或全局变量
        result = repl.run(code)
        return result if result else "代码执行成功（无输出）"
    except Exception as e:
        return f"执行出错: {str(e)}"
