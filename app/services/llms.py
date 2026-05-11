from langchain_openai import ChatOpenAI
from langchain_mistralai import ChatMistralAI
from langchain_cohere import ChatCohere
from app.core.config import config

groq_llm = ChatOpenAI(
    model="llama-3.3-70b-versatile",
    openai_api_key=config.GROQ_API_KEY.get_secret_value(),
    openai_api_base="https://api.groq.com/openai/v1",
    streaming=True,
    max_tokens=5120,
)

mistral_llm = ChatMistralAI(
    model="mistral-small-latest",
    api_key=config.MISTRAL_API_KEY.get_secret_value(),
    streaming=True,
    max_tokens=5120,
)

cohere_llm = ChatCohere(
    model="command-a-03-2025",
    cohere_api_key=config.COHERE_API_KEY.get_secret_value(),
    streaming=True,
    max_tokens=5120,
)

local_llm = ChatOpenAI(
    base_url="http://localhost:8080/v1",
    api_key="test",
    model="mlx-community/gemma-4-e4b-it-4bit",
    streaming=True,
    max_tokens=1024,
)