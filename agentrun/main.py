from typing import Any

from langchain.agents import create_agent
import pydash
import os

from agentrun.integration.langchain import model, sandbox_toolset, AgentRunConverter
from agentrun.sandbox import TemplateType
from agentrun.server import AgentRequest, AgentRunServer
from agentrun.utils.log import logger

# 请替换为您已经创建的 模型 和 沙箱 名称
MODEL_NAME = os.getenv("MODEL_NAME")
MODEL_SERVICE_NAME = os.getenv("MODEL_SERVICE_NAME")
SANDBOX_NAME = os.getenv("SANDBOX_NAME")

if not MODEL_SERVICE_NAME:
    raise ValueError("请将 MODEL_SERVICE_NAME 替换为您已经创建的模型名称")


def invoke_agent(request: AgentRequest):
    input: Any = {"messages": [{"content": message.content, "role": message.role} for message in request.messages]}
    converter = AgentRunConverter()

    try:
        
        #result = agent.invoke(input)
        #return pydash.get(result, "messages.-1.content")
        return "mock response"
    except Exception as e:
        import traceback

        traceback.print_exc()
        logger.error("调用出错: %s", e)
        raise e


AgentRunServer(invoke_agent=invoke_agent).start()
"""
curl 127.0.0.1:9000/openai/v1/chat/completions -XPOST \
    -H "content-type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "写一段代码,查询现在是几点?"}], 
        "stream":true
    }'

curl 127.0.0.1:9000/ag-ui/agent -XPOST \
    -H "content-type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "写一段代码,查询现在是几点?"}]
    }'
"""

