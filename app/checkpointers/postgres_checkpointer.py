from langgraph.checkpoint.postgres import PostgresSaver
import psycopg
from app.core.config import settings

def get_checkpointer() -> PostgresSaver:
    # Use sync psycopg connection for LangGraph checkpointer
    conn = psycopg.connect(settings.CHECKPOINT_DB_URL, autocommit=True)
    checkpointer = PostgresSaver(conn)
    # setup() creates the necessary tables if they don't exist
    checkpointer.setup()
    return checkpointer
