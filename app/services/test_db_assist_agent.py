

from pathlib import Path
from time import perf_counter

from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_groq import ChatGroq
from pydantic import SecretStr
import yaml

from app.core.config import settings

YAML_CONFIG_PATH = Path(__file__).resolve().parents[2] / "db_assist.yaml"

#-------------------------------AgentMetrics-------------------------------
from langchain_core.callbacks import BaseCallbackHandler
class AgentMetrics(BaseCallbackHandler):
    def __init__(self):
        self.llm_calls = 0
        self.tool_calls = 0
        self.tool_results = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.llm_calls += 1

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.llm_calls += 1

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.tool_calls += 1

    def on_tool_end(self, output, **kwargs):
        self.tool_results += 1

    def on_llm_end(self, response, **kwargs):
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                if message is None:
                    continue

                usage = (
                    getattr(message, "usage_metadata", None)
                    or getattr(message, "response_metadata", {}).get("token_usage", {})
                )
                self.input_tokens += usage.get(
                    "input_tokens", usage.get("prompt_tokens", 0)
                )
                self.output_tokens += usage.get(
                    "output_tokens", usage.get("completion_tokens", 0)
                )

def load_database_config() -> tuple[str, list[str]]:
    """Read the PostgreSQL schema and allowed table names from YAML."""
    if not YAML_CONFIG_PATH.is_file():
        raise FileNotFoundError(
            f"YAML config not found: {YAML_CONFIG_PATH}. "
            "Create it using the example at the top of this file."
        )

    with YAML_CONFIG_PATH.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    if not isinstance(config, dict) or not isinstance(config.get("database"), dict):
        raise ValueError("YAML config must contain a 'database' mapping.")

    database_config = config["database"]
    schema = database_config.get("schema")
    tables = database_config.get("tables")
    if not isinstance(schema, str) or not schema.strip():
        raise ValueError("Set a non-empty database.schema in the YAML config.")
    if (
        not isinstance(tables, list)
        or not tables
        or any(not isinstance(table, str) or not table.strip() for table in tables)
    ):
        raise ValueError("database.tables must be a non-empty list of table names.")

    return schema.strip(), [table.strip() for table in tables]



def main() -> None:

    if not settings.DATABASE_URL:
        raise ValueError("Set DATABASE_URL in back_end/.env before running this example.")

    schema_name, table_names = load_database_config()

    database = SQLDatabase.from_uri(settings.DATABASE_URL,include_tables=table_names,)

    llm = ChatGroq(
        model=settings.llm_model_name,
        temperature=0,
        api_key=SecretStr(settings.groq_llm_api_key),
    )


    #-------------------------------SQLDatabaseToolkit-------------------------------
    toolkit = SQLDatabaseToolkit(db=database, llm=llm)
    #tools = {tool.name: tool for tool in toolkit.get_tools()}

    from langchain_community.agent_toolkits.sql.base import create_sql_agent

    agent = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        agent_type="tool-calling",
        verbose=False,
        agent_executor_kwargs={"return_intermediate_steps": True},
    )

    metrics = AgentMetrics()
    started_at = perf_counter()
    agent_result = agent.invoke({"input": "How many customers are in the database?"}, config={"callbacks": [metrics]})
    print("--------------------------------------")
    print(agent_result["output"])

    #--------------------observability--------------------
    print("Observability metrics...", flush=True)
    latency_seconds = perf_counter() - started_at

    print(agent_result["output"])
    print("Observability metrics:")
    print(f"LLM calls: {metrics.llm_calls}")
    print(f"Tool calls: {metrics.tool_calls}")
    print(f"Tool results: {metrics.tool_results}")
    print(f"Input tokens: {metrics.input_tokens}")
    print(f"Output tokens: {metrics.output_tokens}")
    print(f"Agent latency: {latency_seconds:.3f} seconds")

    #--------------------agent memory for tracing--------------------
    print("Tracing agent memory...", flush=True)
    for action, observation in agent_result["intermediate_steps"]:
        print(f"Tool: {action.tool}")
        print(f"Input: {action.tool_input}")
        print(f"Result: {observation}")


if __name__ == "__main__":
    main()
