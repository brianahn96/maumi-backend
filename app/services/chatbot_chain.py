from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage

from app.services.llms import groq_llm, mistral_llm, cohere_llm, local_llm
from app.core.config import config

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str


SYSTEM_PROMPT = """당신은 친절하고 유능한 AI 어시스턴트입니다.
사용자의 질문에 명확하고 도움이 되는 답변을 제공합니다.
한국어로 질문하면 한국어로, 영어로 질문하면 영어로 답변합니다."""

LLM = local_llm if config.ENVIRONMENT == "development" else cohere_llm.with_fallbacks([groq_llm, mistral_llm])

async def chatbot_node(state: ChatState) -> dict:

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    
    full_content = ""
    async for chunk in LLM.astream(messages):
        full_content += chunk.content
        
    return {"messages": [AIMessage(content=full_content)], "session_id": state["session_id"]}


async def should_continue(state: ChatState) -> str:
    return END


def build_graph():
    graph = StateGraph(ChatState)

    graph.add_node("chatbot", chatbot_node)

    graph.add_edge(START, "chatbot")
    graph.add_edge("chatbot", END)

    return graph.compile()

chat_graph = build_graph()