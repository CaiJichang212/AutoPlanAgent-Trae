from typing import Dict, Any
from agent.state import AgentState
from agent.utils import get_model_from_name, setup_logger, load_prompt
import json
import os
import datetime

logger = setup_logger("reporting_node")

def generate_report(state: AgentState) -> Dict[str, Any]:
    """整合所有分析结果，自动生成结构化报告"""
    logger.info("正在生成最终分析报告...")
    llm = get_model_from_name()
    
    understanding = state['understanding']
    context = state['context']
    plan = state['plan']
    
    # 构造分析结果摘要和生成的图表列表
    analysis_results = ""
    generated_images = []
    for step in plan:
        if step['status'] == 'completed':
            output_str = str(step.get('output', ''))
            # 限制单个步骤结果的长度，防止 token 溢出
            if len(output_str) > 3000:
                output_str = output_str[:3000] + "...(数据过长已截断)"
            
            analysis_results += f"### {step['task']}\n- 工具: {step['tool']}\n- 结果: {output_str}\n\n"
            if step['tool'] == 'visualizer':
                # 提取路径
                import re
                # 匹配完整路径
                match = re.search(r'(/Users/lzc/Documents/TNTprojectZ/LangChainStudy/AwesomeLangchainTutorial/AutoPlanAgent/AutoPlanAgent-Trae/reports/images/[^ \n\r\t]+)', output_str)
                if match:
                    img_path = match.group(0)
                    # 清理可能存在的标点符号
                    img_path = img_path.rstrip('。.,')
                    generated_images.append(img_path)

    images_info = "\n".join([f"- 路径: {img}" for img in generated_images]) if generated_images else "（未生成图表）"
    
    # 加载行业调研报告模板
    template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates', 'industry_research.md')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            report_template = f.read()
    except Exception as e:
        logger.warning(f"无法加载报告模板: {str(e)}，将使用默认提示词")
        report_template = "（请根据分析结果生成报告）"

    prompt_template = load_prompt("reporting")
    prompt = prompt_template.format(
        goal=understanding['goal'],
        business_context=understanding['business_context'],
        analysis_results=analysis_results,
        images_info=images_info,
        report_template=report_template
    )
    
    report = llm.invoke(prompt).content
    
    # 保存报告到 reports/files
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"report_{timestamp}.md"
        report_path = os.path.join("reports", "files", report_filename)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"报告已保存至: {report_path}")
    except Exception as e:
        logger.error(f"保存报告失败: {str(e)}")
    
    return {
        "report": report,
        "history": [{"role": "assistant", "content": f"数据分析报告已生成并保存至 {report_path}。"}]
    }
