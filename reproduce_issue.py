"""问题复现脚本，用于测试 PythonREPL 中的代码执行和上下文传递。

该脚本模拟了将 JSON 格式的上下文传递给 PythonREPL 并执行相关数据处理代码的过程。
"""
import json
import pandas as pd
import numpy as np
from langchain_experimental.utilities import PythonREPL

def reproduce():
    """复现并测试 PythonREPL 执行逻辑。"""
    repl = PythonREPL()

    context_json = json.dumps({"step2": [{"a": 1}, {"a": 2}]}, ensure_ascii=False)
    code = """
import json
import pandas as pd
step2_data = context['step2']
df = pd.DataFrame(step2_data)
print(df)
"""

    indented_code = "\n".join(f"    {line}" for line in code.splitlines())
    full_code = f"""
import json
import pandas as pd
import numpy as np

context_str = {repr(context_json)}
context = json.loads(context_str)

try:
{indented_code}
except SystemExit as e:
    print(json.dumps({{"warning": "exit", "detail": str(e)}}))
"""

    print("--- Full Code ---")
    print(full_code)
    print("--- Execution Result ---")
    result = repl.run(full_code)
    print(result)

if __name__ == "__main__":
    reproduce()
