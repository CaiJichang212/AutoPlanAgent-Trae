
import json
import pandas as pd
import numpy as np
from langchain_experimental.utilities import PythonREPL

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
