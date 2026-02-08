"""JSON 提取逻辑测试脚本。

该脚本用于测试从包含杂乱文本的字符串中提取最后一个有效的 JSON 对象（特别是包含特定业务字段的对象）的算法。
"""
import json
import re

def extract_last_json(text: str):
    """从文本中提取最后一个有效的 JSON 对象。

    Args:
        text: 包含潜在 JSON 字符串的文本。

    Returns:
        提取出的字典或列表对象，如果未找到则返回 None。
    """
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

def run_test():
    """执行提取逻辑的测试用例。"""
    # 测试用例
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

if __name__ == "__main__":
    run_test()
