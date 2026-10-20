# Product Data Copilot: what it is, how it works, and why it's built this way

## The 30-second pitch

> "At Samsara I owned product data: SKUs, BOMs and spec sheets across Propel, NetSuite and E2open. I chased missing and stale BOMs by hand and grew a product information tracker from 32 to 390+ users. Product Data Copilot is that problem rebuilt on Databricks, end to end. It reads spec-sheet PDFs with Document Intelligence, builds a governed gold layer with an owner on every SKU, defines quality metrics once in a Unity Catalog metric view, and puts a multi-step agent on top as a Databricks App. The agent finds the issues, proves them with evidence, has its own work reviewed, and files fix tasks to the right owner only after a human confirms."

## Why this project

1. **It's my real experience.** Interviewers ask follow-ups, and every follow-up here is something I've actually done: BOM remediation, spec mismatches, owners, lifecycle (NPI, GA, EOL), and adoption.
2. **It follows Databricks' own reference architecture.** Each box in their diagram has a working piece (see the table below), so the demo shows I understand how the platform fits together, not just one feature.
3. **It matches the job posting.** The posting asks for pipelines, metric definitions, dashboards and Genie, Databricks Apps, agentic workflows, and early adoption of new features. This project touches all of them.
4. **It's honest.** The data is fictional (Vela Devices), so nothing from Samsara is exposed, but the problems are realistic ones.

## Architecture, layer by layer

| Diagram layer | What I built | Why this choice |
|---|---|---|
| **Enterprise data** | `skus`, `components`, `bom_lines`, `product_line_owners`, plus 12 spec-sheet PDFs in a UC Volume | Real product data is split between structured tables and unstructured documents. The interesting problems sit where the two disagree. |
| **Prepare and connect** | `ai_parse_document` turns the PDFs into layout-aware elements. `ai_extract` pulls typed fields against a JSON schema, with an enum for lifecycle. | Native SQL functions, so there's no extra service to run. The schema constrains the output: weight comes back as an integer and lifecycle can only be NPI, GA or EOL. That makes the output joinable and testable instead of free text. |
| **Trusted foundation** | `sku_gold` (cleaned keys, owner on every row, `requires_bom` flag), governance tags, Delta Change Data Feed on the SKU master | Ownership is what turns a finding into an action. CDF gives an audit trail of who changed what, which is the "track changes" box. |
| **Business meaning** | `spec_mismatches` view, `sku_data_quality` view with a documented `quality_score`, and the `product_data_metrics` UC metric view | **Metrics are defined once, in SQL, not by the LLM.** The score rules (-40 missing BOM on a GA SKU, -20 stale BOM, -20 obsolete part, -10 NRND part, -10 per spec mismatch) live in one governed place. Genie, dashboards and the agent all read the same numbers. |
| **Ask and analyze** | A Genie space on the metric view and quality tables, with instructions such as "never recompute quality_score" | Business users get self-serve questions like "BOM completeness by product line" without new dashboards. The instructions keep Genie on the governed definitions. |
| **Build and automate** | A multi-step agent (OpenAI Agents SDK, on Databricks' official app template) | Covered in the next section. |
| **Deliver** | A Databricks App with a chat UI and a `/responses` API | It deploys with one bundle command, runs as a service principal, and is governed by Unity Catalog. |
| **Governance (cross-cutting)** | Unity Catalog permissions on tables and functions, app resources in `databricks.yml`, the model served through Unity Gateway | Every arrow in the diagram passes through Unity Catalog. The app can only touch what it's granted. |

## How the agent works, and why

The agent runs six steps:

1. **Scorecard.** It calls `get_data_quality("all")`, a UC SQL function over `sku_data_quality`. The agent never computes scores; it reads the governed ones.
2. **Analysis.** It asks Genie (through Genie's managed MCP server) for rollups, such as completeness by product line.
3. **Evidence.** It calls `get_sku_details(sku)` for each flagged SKU to get the BOM lines, component lifecycle, and spec mismatches with the source PDF file name. Every claim is tied to evidence.
4. **Draft.** It writes the issues by severity, each with an owner and a proposed fix.
5. **Review.** A separate reviewer agent checks every SKU, number and owner in the draft against the raw tool outputs. This guards against hallucination.
6. **Action.** It asks which fixes to file. Only after the user confirms does it call `create_fix_task`, which runs a **parameterized** INSERT into `data_fix_tasks` assigned to the owner's email.

**Design principles behind this:**
- **Deterministic where it matters, generative where it helps.** SQL does the scoring and lookups, and the LLM handles orchestration and writing. That makes the output auditable and repeatable.
- **Tools are UC functions, not prompt text.** They're governed, versioned, reusable by Genie and other agents, and testable on their own in the SQL editor.
- **Human-in-the-loop for writes.** Reading is automatic. Writing needs a confirmation.
- **Parameterized SQL** in the write tool, so model output can't inject SQL.
- **Graceful degradation.** If the Genie connection fails, the agent drops it, keeps working, and says which source is unavailable.
- **Observability.** Every run is traced in MLflow (the `agents-on-apps` experiment), so you can see each tool call and its latency and evaluate quality over time.

## Problems I hit and how I solved them (good interview stories)

| Problem | Root cause | Fix and lesson |
|---|---|---|
| No Claude model on Free Edition | Model availability differs by workspace tier | The model name is a config value (`LLM_ENDPOINT`), served through Unity Gateway. Swapping models is a config change, not a rewrite. |
| Qwen 3.5 crashed the response parser | It's a reasoning model and returns reasoning blocks the Agents SDK's chat-completions path can't read | Used an **instruct** (non-reasoning) model. The lesson is to check model output formats against your framework, not just the benchmarks. |
| Llama 3.3 wrote `<function=...>` as text instead of calling tools, and listed a healthy SKU as broken | Weaker tool-calling reliability | Switched to Qwen3 Next Instruct. This is why the reviewer step exists, and why models should be evaluated on your own task. |
| UC function tools failed through the managed MCP connection on Free Edition | A platform or tier limitation in that path | Called the same UC functions through the SQL Statement Execution API on my warehouse. Same governed functions, more reliable path. |
| The agent invented a part number ("C-IMG-2M-V2") | The LLM filled a gap | Added a rule: never invent IDs, say "a qualified Active alternate" instead. Guardrails come from observed failures. |
| Python 3.15 build failure | Too-new interpreter with no prebuilt wheels | Pinned Python 3.12 with `uv python pin`. |
| Bundle deploy errors (placeholders, missing Genie name) | Config drift between local copies | Validate before deploying, and keep config in one place. |

## What I'd do next with more time

- **Schedule it.** Run the parsing and gold-layer SQL as a Lakeflow job, so new PDFs are processed nightly.
- **Evaluation set.** Write 20 questions with expected answers, run `mlflow.genai.evaluate` with correctness and groundedness judges, and track the scores across model swaps.
- **Agent Bricks.** Rebuild the orchestrator as an Agent Bricks supervisor over the Genie space and UC functions, and compare it with the code version.
- **On-behalf-of user auth.** Have the app act with the viewer's own permissions instead of a shared service principal.
- **Lakebase.** Store chat history and fix-task status for a live workflow UI.
- **Close the loop.** Re-score after owners fix their issues, and show quality improving over time on a dashboard.

## Likely interview questions

- **"Why not let the LLM compute the score?"** Numbers that drive decisions must be reproducible and governed. The LLM explains them; SQL computes them.
- **"Why Genie and custom tools?"** Genie handles open-ended analytics questions. Typed tools handle precise, repeatable lookups and actions. Each does what it's best at.
- **"How do you stop hallucinations?"** Tools return facts, a reviewer agent checks the draft against raw outputs, there are prompt rules from observed failures, and MLflow traces let you audit any answer.
- **"How would this scale to 50,000 SKUs?"** The SQL already runs set-based on a warehouse. Tool outputs would be paginated or filtered by product line, with Genie handling aggregates.
- **"What would you tell a partner building on Databricks?"** Start from the app template, keep metrics in UC, expose tools as UC functions, trace everything in MLflow, and treat the model as a swappable config.
