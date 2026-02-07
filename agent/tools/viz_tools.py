import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import os
import json
import ast
import re
from langchain_core.tools import tool
from typing import Dict, Any

# 设置中文字体支持（如果环境支持）
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

@tool
def visualizer(plot_code: str, filename: str) -> str:
    """
    根据提供的 matplotlib/seaborn 代码生成图表。
    plot_code: 绘图的 python 代码。
    filename: 保存图片的文件名（建议仅提供文件名，如 'plot.png'）。
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
        plot_code = plot_code.get("plot_code", "")
    if isinstance(plot_code, str) and '"plot_code"' in plot_code:
        try:
            embedded = json.loads(plot_code)
            if not filename and isinstance(embedded, dict):
                filename = embedded.get("filename", filename)
            if isinstance(embedded, dict) and "plot_code" in embedded:
                plot_code = embedded.get("plot_code", "")
        except Exception:
            try:
                embedded = ast.literal_eval(plot_code)
                if not filename and isinstance(embedded, dict):
                    filename = embedded.get("filename", filename)
                if isinstance(embedded, dict) and "plot_code" in embedded:
                    plot_code = embedded.get("plot_code", "")
            except Exception:
                pass
    if not isinstance(plot_code, str):
        plot_code = str(plot_code)
    plot_code = re.sub(r"^```[a-zA-Z]*\n", "", plot_code).replace("```", "")
    plot_code = re.sub(r'plt\.savefig\(.*?\)', '', plot_code)
    
    # 构造完整的执行代码
    full_code = "\n".join([
        "import matplotlib",
        "matplotlib.use('Agg')",
        "import matplotlib.pyplot as plt",
        "import seaborn as sns",
        "import pandas as pd",
        "import platform",
        "system = platform.system()",
        "if system == 'Darwin':",
        "    fonts = ['Arial Unicode MS', 'PingFang HK', 'Heiti TC', 'sans-serif']",
        "elif system == 'Windows':",
        "    fonts = ['SimHei', 'Microsoft YaHei', 'sans-serif']",
        "else:",
        "    fonts = ['WenQuanYi Micro Hei', 'Droid Sans Fallback', 'sans-serif']",
        "plt.rcParams['font.sans-serif'] = fonts",
        "plt.rcParams['axes.unicode_minus'] = False",
        "sns.set_style('whitegrid', {'font.sans-serif': fonts})",
        plot_code,
        f"plt.savefig('{filepath}')",
        "plt.close()"
    ])
    try:
        from langchain_experimental.utilities import PythonREPL
        repl = PythonREPL()
        repl_output = repl.run(full_code)
        if os.path.exists(filepath):
            return f"图表已生成并保存至: {filepath}"
        else:
            return f"绘图失败: 文件未生成。REPL 输出: {repl_output}"
    except Exception as e:
        return f"绘图出错: {str(e)}"
