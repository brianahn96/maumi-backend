from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_mistralai import ChatMistralAI
from langchain_cohere import ChatCohere
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage

from app.core.config import config

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str


# Primary LLM (Groq)
groq_fallback = ChatOpenAI(
    model="llama-3.3-70b-versatile",
    openai_api_key=config.GROQ_API_KEY.get_secret_value(),
    openai_api_base="https://api.groq.com/openai/v1",
    max_tokens=1024,
    streaming=True,
)

# Fallback 1: Mistral (Direct)
mistral_fallback = ChatMistralAI(
    model="mistral-small-latest",
    api_key=config.MISTRAL_API_KEY.get_secret_value(),
    max_tokens=1024,
)

# Fallback 2: Cohere (Direct)
cohere_llm = ChatCohere(
    model="command-a-03-2025",
    cohere_api_key=config.COHERE_API_KEY.get_secret_value(),
    max_tokens=1024,
)

# Chain with fallbacks
llm = cohere_llm.with_fallbacks([mistral_fallback, groq_fallback])

SYSTEM_PROMPT = """당신은 친절하고 유능한 AI 어시스턴트입니다.
사용자의 질문에 명확하고 도움이 되는 답변을 제공합니다.
한국어로 질문하면 한국어로, 영어로 질문하면 영어로 답변합니다."""

async def chatbot_node(state: ChatState) -> dict:
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    
    full_content = ""
    async for chunk in llm.astream(messages):
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