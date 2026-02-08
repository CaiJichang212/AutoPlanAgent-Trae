"""可视化工具，提供图表生成和保存功能。

该模块使用 matplotlib 和 seaborn 生成图表，并根据运行平台自动配置中文字体。
生成的图表会保存到项目的 reports/images 目录下。
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import os
import json
import ast
import re
import io
import sys
from langchain_core.tools import tool
from typing import Dict, Any

# 设置中文字体支持（如果环境支持）
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

from agent.tools.analysis_tools import shared_scope
from langchain_experimental.utilities import PythonREPL

@tool
def visualizer(plot_code: str, filename: str, context: Dict[str, Any] = None) -> str:
    """根据提供的 matplotlib/seaborn 代码生成图表。

    Args:
        plot_code: 绘图的 python 代码。
        filename: 保存图片的文件名（建议仅提供文件名，如 'plot.png'）。
        context: 前序步骤的上下文数据。

    Returns:
        JSON 格式的结果字符串，包含状态、保存路径和执行输出。
    """
    # 获取项目根目录 (agent/tools/viz_tools.py -> agent/tools/ -> agent/ -> root/)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    save_dir = os.path.join(project_root, "reports", "images")
    os.makedirs(save_dir, exist_ok=True)
    
    # 强制提取纯文件名，防止 LLM 生成路径导致保存位置错误
    pure_filename = os.path.basename(filename)
    filepath = os.path.join(save_dir, pure_filename)
    
    if isinstance(plot_code, dict):
        if not filename and "filename" in plot_code:
            filename = plot_code.get("filename")
        plot_code = plot_code.get("plot_code") or plot_code.get("code") or ""
    
    if not isinstance(plot_code, str):
        plot_code = str(plot_code)

    # 尝试解析可能被双重包装的 JSON
    if plot_code.strip().startswith("{"):
        try:
            embedded = json.loads(plot_code)
            if isinstance(embedded, dict):
                plot_code = embedded.get("plot_code") or embedded.get("code") or plot_code
                if not filename:
                    filename = embedded.get("filename", filename)
        except Exception:
            pass
    
    # 进一步清理 plot_code
    # 移除 markdown 标记
    plot_code = re.sub(r"^```[a-zA-Z]*\n", "", plot_code).replace("```", "").strip()
    # 移除 LLM 可能误生成的 plt.show() 或 plt.savefig()
    plot_code = re.sub(r'plt\.show\(.*?\)', '', plot_code)
    plot_code = re.sub(r'plt\.savefig\(.*?\)', '', plot_code)
    
    if not filename:
        filename = "plot.png"
    
    # 强制提取纯文件名
    pure_filename = os.path.basename(filename)
    if not pure_filename.endswith(('.png', '.jpg', '.jpeg', '.pdf', '.svg')):
        pure_filename += '.png'
    filepath = os.path.join(save_dir, pure_filename)
    
    # 使用共享作用域
    # 注入上下文到 shared_scope 以供绘图代码访问
    shared_scope['context'] = context
    
    # 构建执行代码
    full_code = f"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import json
import platform
from agent.tools.analysis_tools import shared_scope

# 注入全局作用域，解决 lambda 作用域问题
shared_scope['plt'] = plt
shared_scope['sns'] = sns
shared_scope['pd'] = pd
shared_scope['np'] = np

# 设置字体
system = platform.system()
if system == 'Darwin':
    fonts = ['Arial Unicode MS', 'PingFang HK', 'Heiti TC', 'sans-serif']
elif system == 'Windows':
    fonts = ['SimHei', 'Microsoft YaHei', 'sans-serif']
else:
    fonts = ['WenQuanYi Micro Hei', 'Droid Sans Fallback', 'sans-serif']
plt.rcParams['font.sans-serif'] = fonts
plt.rcParams['axes.unicode_minus'] = False
sns.set_style('whitegrid', {{'font.sans-serif': fonts}})

# 执行绘图代码
try:
{ "\n".join("    " + line for line in plot_code.splitlines()) }
    plt.savefig({repr(filepath)})
    plt.close()
    print(json.dumps({{"status": "success", "path": {repr(filepath)}}}, ensure_ascii=False))
except Exception as e:
    import traceback
    error_info = {{
        "error": str(e),
        "type": type(e).__name__,
        "traceback": traceback.format_exc()
    }}
    print(json.dumps(error_info, ensure_ascii=False))
"""
    
    # 执行代码
    try:
        output_buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output_buffer
        try:
            # 同样使用 shared_scope 作为 globals 和 locals
            exec(full_code, shared_scope, shared_scope)
        finally:
            sys.stdout = old_stdout
        
        repl_output = output_buffer.getvalue()
        # 尝试从输出中提取 JSON 结果
        if os.path.exists(filepath):
            return json.dumps({"status": "success", "path": filepath, "repl_output": repl_output}, ensure_ascii=False)
        else:
            return json.dumps({"error": f"绘图失败: 文件未生成", "repl_output": repl_output}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"绘图执行出错: {str(e)}"}, ensure_ascii=False)
