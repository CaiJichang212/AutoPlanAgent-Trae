from agent.graph import graph
import uuid

def run_test():
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # 1. 启动任务
    print("--- 1. 启动任务 ---")
    query = "分析光伏行业公司2024-2025年基本面情况？"
    initial_state = {"input": query}
    
    for event in graph.stream(initial_state, config):
        for node, values in event.items():
            print(f"Node: {node}")
            if node == "understand":
                print(f"理解结果: {values['understanding']['goal']}")
            if node == "plan":
                print(f"规划了 {len(values['plan'])} 个步骤")
            print(values)
            

    # 2. 模拟用户确认
    print("\n--- 2. 用户确认 ---")
    # 此时图处于 handle_feedback 之前的 interrupt 状态
    graph.update_state(config, {"history": [{"role": "user", "content": "同意执行，请开始。"}]})
    
    for event in graph.stream(None, config):
        for node, values in event.items():
            print(f"Node: {node}")
            if node == "execute":
                # 打印执行成功的步骤名
                plan = values.get('plan', [])
                idx = values.get('current_step_index', 0) - 1
                if idx >= 0:
                    print(f"执行完成步骤: {plan[idx]['task']}")
            if node == "report":
                print("\n--- 最终报告 ---")
                print(values['report'])
            print(values)

if __name__ == "__main__":
    run_test()
