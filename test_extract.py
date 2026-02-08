import json
import re

def extract_last_json(text: str):
    if not isinstance(text, str):
        return None
    
    results = []
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
                            results.append(val)
                            break
                        except Exception:
                            pass
    
    if not results:
        return None
        
    for res in reversed(results):
        if isinstance(res, dict):
            if any(k in res for k in ('data', 'cleaned_data', 'result', 'rankings', 'composite_score')):
                return res
                
    return results[-1]

# Test cases
test_text = """
Some debug info
{"outlier_summary": {"col1": 1}}
More debug info
{"data": [{"a": 1}, {"a": 2}], "summary": "done"}
Final text
"""

result = extract_last_json(test_text)
print(f"Extracted: {result}")
assert result['summary'] == "done"
print("Test passed!")
