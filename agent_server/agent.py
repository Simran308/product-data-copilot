"""Product Data Copilot: a multi-step product data quality agent on Databricks.

Drop-in replacement for agent_server/agent.py in the databricks/app-templates
`agent-openai-agents-sdk` template.
Modified by Simran Sharma from databricks/app-templates (see third_party/databricks-app-templates).
The orchestrator works in fixed steps:
  1. Scorecard   -> get_data_quality UC function (governed quality checks and score), run on the SQL warehouse
  2. Analysis    -> Genie space over the product_data_metrics metric view and tables
  3. Evidence    -> get_sku_details UC function (BOM lines, component lifecycle, spec-sheet mismatches)
  4. Review      -> a reviewer sub-agent checks every claim in the draft against the raw data
  5. Action      -> create_fix_task writes owner-assigned fix tasks to a Delta table (after the user confirms)
"""


import logging
import os
from contextlib import AsyncExitStack
from datetime import date
from typing import AsyncGenerator

import mlflow
from agents import Agent, Runner, function_tool, set_default_openai_api, set_default_openai_client
from agents.tracing import set_trace_processors
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from agent_server.history import normalize_history_items
from agent_server.utils import build_mcp_url, get_session_id, process_agent_stream_events

logger = logging.getLogger(__name__)

# Use any chat model listed on your workspace's Serving page; keep databricks.yml in sync.
MODEL = os.getenv("LLM_ENDPOINT", "databricks-qwen3-next-80b-a3b-instruct")
CATALOG_SCHEMA = os.getenv("PRODUCT_SCHEMA", "workspace.product_data")
GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "")

set_default_openai_client(AsyncDatabricksOpenAI())
set_default_openai_api("chat_completions")
set_trace_processors([])  # only use mlflow for trace processing
mlflow.openai.autolog()
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)


def _run_sql(statement: str, params: dict[str, str]) -> str:
    """Run one SQL statement on the warehouse and return the first column of the first row."""
    w = WorkspaceClient()
    resp = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=statement,
        parameters=[StatementParameterListItem(name=k, value=v) for k, v in params.items()],
        wait_timeout="50s",
    )
    state = resp.status.state.value if resp.status and resp.status.state else "UNKNOWN"
    if state != "SUCCEEDED":
        error = resp.status.error.message if resp.status and resp.status.error else ""
        return f"Query failed ({state}): {error}"
    rows = resp.result.data_array if resp.result else None
    return rows[0][0] if rows and rows[0][0] is not None else "No matching rows."


@function_tool
def get_data_quality(query: str) -> str:
    """Per-SKU data quality checks and quality_score as JSON, lowest score first.
    query is a SKU (e.g. CM-10), a product line (Gateways, Cameras, Sensors, Cables, Accessories, Licenses), or "all"."""
    return _run_sql(f"SELECT {CATALOG_SCHEMA}.get_data_quality(:q)", {"q": query})


@function_tool
def get_sku_details(sku: str) -> str:
    """SKU master record, BOM lines with component lifecycle, and spec-sheet mismatches as JSON. sku is e.g. CM-20."""
    return _run_sql(f"SELECT {CATALOG_SCHEMA}.get_sku_details(:s)", {"s": sku})


@function_tool
def create_fix_task(sku: str, issue: str, proposed_fix: str, owner_email: str) -> str:
    """Create a data fix task for a SKU, assigned to the product line's data owner.
    Only call this after the user has confirmed the task. owner_email must come from the tool data."""
    w = WorkspaceClient()
    resp = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=(
            f"INSERT INTO {CATALOG_SCHEMA}.data_fix_tasks "
            "VALUES (:sku, :issue, :fix, :owner, current_timestamp(), 'open')"
        ),
        parameters=[
            StatementParameterListItem(name="sku", value=sku),
            StatementParameterListItem(name="issue", value=issue),
            StatementParameterListItem(name="fix", value=proposed_fix),
            StatementParameterListItem(name="owner", value=owner_email),
        ],
        wait_timeout="30s",
    )
    state = resp.status.state.value if resp.status and resp.status.state else "UNKNOWN"
    return f"Insert status: {state}"


reviewer = Agent(
    name="Reviewer",
    model=MODEL,
    instructions=(
        "You review a draft product data quality report. The input contains the raw tool outputs and the draft. "
        "Check every SKU, number, status and owner in the draft against the raw tool outputs. "
        "Reply 'APPROVED' if everything is supported. Otherwise list each unsupported or wrong "
        "claim and the corrected value from the data."
    ),
)


def build_mcp_servers(w: WorkspaceClient) -> list[McpServer]:
    servers = []
    if GENIE_SPACE_ID:
        servers.append(
            McpServer(
                url=build_mcp_url(f"/api/2.0/mcp/genie/{GENIE_SPACE_ID}", workspace_client=w),
                name="Product data Genie space",
                workspace_client=w,
            )
        )
    return servers


async def connect_healthy_mcp_servers(
    stack: AsyncExitStack, servers: list[McpServer]
) -> tuple[list[McpServer], list[str]]:
    """Connect each MCP server and drop any that cannot list its tools (from the template)."""
    healthy: list[McpServer] = []
    unavailable: list[str] = []
    for server in servers:
        name = getattr(server, "name", "MCP server")
        try:
            connected = await stack.enter_async_context(server)
            await connected.list_tools()
            healthy.append(connected)
        except Exception:
            logger.warning("MCP server %r unavailable; continuing without it.", name, exc_info=True)
            unavailable.append(name)
    return healthy, unavailable


def create_agent(mcp_servers: list[McpServer], unavailable: list[str]) -> Agent:
    instructions = f"""You are Product Data Copilot for Vela Devices' product data governance team.
You help keep SKU, BOM and spec-sheet data correct. Today is {date.today().isoformat()}.

For a data quality question, work in these steps and say which step you are on:
1. Scorecard: call get_data_quality with a SKU, a product line, or "all". These are the official checks
   and quality_score; never compute scores yourself.
2. Analysis: for rollups and trends (BOM completeness by product line, counts by owner), ask the Genie
   space a precise question. It uses the product_data_metrics metric view.
3. Evidence: for each SKU you will flag, call get_sku_details to see its BOM lines, component lifecycle
   (Obsolete, NRND) and any spec-sheet mismatches with the source PDF file name.
4. Draft: list the issues by severity (missing BOM on a GA SKU, obsolete parts, stale BOM, spec-sheet
   mismatch), with the evidence, the owner, and a concrete proposed fix for each.
5. Review: pass the raw tool outputs and your draft to the Reviewer tool. Fix anything it flags.
6. Action: ask the user which fixes to file. Only after they confirm, call create_fix_task once per fix,
   using the owner_email from the tool data.

Use only facts returned by tools. Never invent part numbers or component IDs; if a replacement part is
needed, say "a qualified Active alternate". If a tool fails, say so instead of guessing."""
    if unavailable:
        instructions += f"\nThese data sources are unavailable right now: {', '.join(unavailable)}."
    return Agent(
        name="Product Data Copilot",
        model=MODEL,
        instructions=instructions,
        tools=[
            get_data_quality,
            get_sku_details,
            create_fix_task,
            reviewer.as_tool(
                tool_name="Reviewer",
                tool_description="Fact-checks a draft brief against raw tool outputs.",
            ),
        ],
        mcp_servers=mcp_servers,
    )


async def _build(stack: AsyncExitStack) -> Agent:
    # WorkspaceClient() uses the app's service principal when deployed.
    servers, unavailable = await connect_healthy_mcp_servers(stack, build_mcp_servers(WorkspaceClient()))
    return create_agent(servers, unavailable)


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
    async with AsyncExitStack() as stack:
        agent = await _build(stack)
        messages = normalize_history_items([i.model_dump() for i in request.input])
        result = await Runner.run(agent, messages, max_turns=20)
        return ResponsesAgentResponse(output=[item.to_input_item() for item in result.new_items])


@stream()
async def stream_handler(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
    async with AsyncExitStack() as stack:
        agent = await _build(stack)
        messages = normalize_history_items([i.model_dump() for i in request.input])
        result = Runner.run_streamed(agent, input=messages, max_turns=20)
        async for event in process_agent_stream_events(result.stream_events()):
            yield event
