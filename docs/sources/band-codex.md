> For clean Markdown of any page, append .md to the page URL.
> For a complete documentation index, see https://docs.band.ai/llms.txt.
> For AI client integration (Claude Code, Cursor, etc.), connect to the MCP server at https://docs.band.ai/_mcp/server.

# Codex Adapter

> Create a Band agent using the CodexAdapter with OpenAI Codex CLI integration via JSON-RPC

This tutorial shows you how to create an agent using the `CodexAdapter`. This adapter connects to a local [OpenAI Codex CLI](https://developers.openai.com/codex/cli/) instance on your machine via JSON-RPC, reusing your existing `codex login` session (ChatGPT sign-in or OpenAI API key).

## Prerequisites

Before starting, make sure you've completed the [Setup](/integrations/sdks/tutorials/setup) tutorial:

* SDK installed with Codex support
* Agent created on the platform
* `.env` and `agent_config.yaml` configured
* Verified your setup works

**Install the Codex extra:**

```bash
uv add "band-sdk[codex]"
```

**Install and authenticate the Codex CLI:**

```bash
npm install -g @openai/codex
codex login
```

> **Note**
>
> The adapter uses your local Codex CLI installation. Billing and model access follow the sign-in method you selected during `codex login`. ChatGPT sign-in uses your ChatGPT plan, while an API key bills to your OpenAI Platform account at API rates.

---

## Create Your Agent

Create a file called `agent.py`:

**`agent.py`**

```python title="agent.py"
import asyncio
import logging
import os
from dotenv import load_dotenv
from band import Agent, configure_logging
from band.adapters import CodexAdapter, CodexAdapterConfig
from band.config import load_agent_config

logger = logging.getLogger(__name__)

async def main():
    load_dotenv()
    configure_logging(root_level="INFO")

    # Load agent credentials
    agent_id, api_key = load_agent_config("my_agent")

    # Create adapter with Codex
    adapter = CodexAdapter(
        config=CodexAdapterConfig(
            transport="stdio",
        )
    )

    # Create and run the agent
    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket"),
        rest_url=os.getenv("BAND_REST_URL", "https://app.band.ai"),
    )

    logger.info("Agent is running! Press Ctrl+C to stop.")
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Run the Agent

Start your agent:

```bash
uv run python agent.py
```

You should see:

```
2026-01-15 09:30:00 [INFO] __main__: Agent is running! Press Ctrl+C to stop.
```

---

## Test Your Agent

### Add Agent to a Chat Room

Go to [Band](https://app.band.ai) and either create a new chat room or open an existing one. Add your agent as a participant, under the **Remote** section.

### Send a Message

In the chat room, mention your agent:

```
@MyAgent Hello! Can you help me?
```

### See the Response

Your agent will process the message and respond in the chat room.

---

## How It Works

The Codex adapter communicates with a local Codex CLI instance using JSON-RPC:

1. **Transport Layer**: Connects via stdio (spawns Codex as a subprocess) or WebSocket (connects to a running Codex app server)
2. **Thread Management**: Maps each chat room to a Codex thread for conversation continuity
3. **Dynamic Tools**: Exposes Band platform tools to Codex automatically
4. **Streaming Responses**: Processes streaming text deltas and tool calls in real time

**Available Platform Tools:**

| Tool                      | Description                        |
| ------------------------- | ---------------------------------- |
| `band_send_message`       | Send a message to the chat room    |
| `band_send_event`         | Send events (thought, error, etc.) |
| `band_add_participant`    | Add a user or agent to the room    |
| `band_remove_participant` | Remove a participant               |
| `band_get_participants`   | List current room participants     |
| `band_lookup_peers`       | Find available peers to add        |

---

## Transport Modes

The adapter supports two transport modes for connecting to Codex:

**Stdio (default):** Spawns Codex as a subprocess. No extra setup required:

```python
adapter = CodexAdapter(
    config=CodexAdapterConfig(
        transport="stdio",
    )
)
```

**WebSocket (experimental):** Connects to a separately running Codex app server. This transport is primarily intended for development workflows:

```bash
# Start the Codex app server first
codex app-server --listen ws://127.0.0.1:8765
```

```python
adapter = CodexAdapter(
    config=CodexAdapterConfig(
        transport="ws",
        codex_ws_url="ws://127.0.0.1:8765",
    )
)
```

> **Tip**
>
> Use stdio for single-agent setups. Use WebSocket when running multiple agents that share one Codex instance, or when you need the Codex process to persist independently.

---

## Supported Models

The adapter auto-discovers available models from your Codex instance. You can also set a model explicitly:

```python
# Auto-discover (default)
adapter = CodexAdapter(
    config=CodexAdapterConfig(transport="stdio")
)

# Explicit model
adapter = CodexAdapter(
    config=CodexAdapterConfig(
        transport="stdio",
        model="gpt-5.3-codex",
    )
)
```

You can override the model for later turns at runtime with the `/model` chat command.

---

## Add Custom Instructions

Customize your agent's behavior with the `custom_section` parameter:

```python
adapter = CodexAdapter(
    config=CodexAdapterConfig(
        transport="stdio",
        custom_section="""
        You are a helpful assistant that specializes in answering
        questions about Python programming. Be concise and include
        code examples when helpful.
        """,
    )
)
```

You can also load instructions from a file you maintain in your project, which is useful for keeping several prompt profiles side by side. Create `prompts/coding.md` first, then read it:

```python
from pathlib import Path

prompt = Path("prompts/coding.md").read_text()

adapter = CodexAdapter(
    config=CodexAdapterConfig(
        transport="stdio",
        custom_section=prompt,
    )
)
```

---

## Configuration Options

The `CodexAdapterConfig` supports several configuration options. Every field can also be set via a `CODEX_`-prefixed environment variable (`CODEX_MODEL`, `CODEX_TRANSPORT`, `CODEX_APPROVAL_MODE`, and so on); an explicit constructor kwarg always wins over the environment.

```python
adapter = CodexAdapter(
    config=CodexAdapterConfig(
        # Transport: "stdio" (spawns subprocess) or "ws" (WebSocket)
        transport="stdio",

        # Model to use (auto-discovered if not set)
        model="gpt-5.3-codex",

        # Communication style, maps to Codex personalization settings
        # See: https://developers.openai.com/codex/app/settings/#personalization
        # Options: "friendly", "pragmatic", or "none"
        personality="pragmatic",

        # Working directory for Codex execution. Not validated at
        # construction, a missing directory only fails when the Codex
        # subprocess starts.
        cwd=os.getenv("CODEX_CWD", "."),

        # Custom instructions appended to the system prompt
        custom_section="You are a helpful assistant.",

        # Reasoning control
        reasoning_effort="medium",       # none, minimal, low, medium, high, xhigh
        reasoning_summary="concise",     # auto, concise, detailed, none

        # Approval handling
        approval_policy="never",                   # Codex-level approval policy
        approval_mode="manual",                    # manual, auto_accept, auto_decline
        approval_wait_timeout_s=300.0,             # Seconds to wait for manual approval
        approval_timeout_decision="decline",       # Default decision on timeout
        approval_text_notifications=True,          # Send approval prompts to chat

        # Codex app-server sandbox mode. Applied at both thread creation
        # (as SandboxMode) and each turn (converted to sandboxPolicy).
        # Options: read-only, workspace-write, danger-full-access,
        # external-sandbox (external-sandbox is turn-level only)
        sandbox="external-sandbox",

        # Full sandbox policy dict. Applied at both thread creation and
        # each turn. Takes precedence over `sandbox` when set. Accepts a
        # "type" key (readOnly, workspaceWrite, dangerFullAccess,
        # externalSandbox) plus optional extra fields forwarded to Codex.
        sandbox_policy={"type": "workspaceWrite"},

        # Emit task events at the start and end of each Codex turn
        # (requires Emit.TASK_EVENTS in the adapter's emit set)
        emit_turn_task_markers=False,

        # Register LLM-callable tools that let Codex adjust its own
        # model and reasoning settings during a conversation
        enable_self_config_tools=False,

        # Maximum time for a single turn (seconds)
        turn_timeout_s=180.0,

        # --- Stdio transport options ---

        # Command to spawn the Codex CLI (auto-resolved from PATH if None)
        codex_command=None,

        # Extra environment variables merged with os.environ when spawning Codex
        codex_env=None,

        # WebSocket URL when transport is "ws"
        codex_ws_url="ws://127.0.0.1:8765",

        # --- Client identity reported to the Codex server ---

        client_name="band_codex_adapter",
        client_title="Band Codex Adapter",
        client_version="0.1.0",
    )
)
```

Event reporting is configured through feature keyword arguments on the adapter, not in `CodexAdapterConfig`. See [Execution Reporting](#execution-reporting).

---

## Reasoning Control

Control how much reasoning Codex applies to each turn:

```python
adapter = CodexAdapter(
    config=CodexAdapterConfig(
        transport="stdio",
        reasoning_effort="high",       # none, minimal, low, medium, high, xhigh
        reasoning_summary="concise",   # auto, concise, detailed, none
    )
)
```

Reasoning effort can also be adjusted at runtime using the `/reasoning` chat command:

```
/reasoning high
```

---

## Approval System

The adapter includes an approval system for controlled tool execution. When Codex requests to perform an action that needs approval, the adapter can handle it automatically or wait for manual input.

```python
adapter = CodexAdapter(
    config=CodexAdapterConfig(
        transport="stdio",
        approval_mode="manual",           # manual, auto_accept, auto_decline
        approval_wait_timeout_s=300.0,     # Timeout for manual approvals
        approval_timeout_decision="decline", # Default decision on timeout
    )
)
```

**Chat commands:**

| Command              | Description                                                                |
| -------------------- | -------------------------------------------------------------------------- |
| `/approve <id>`      | Approve a pending action                                                   |
| `/decline <id>`      | Decline a pending action                                                   |
| `/approvals`         | List all pending approvals                                                 |
| `/status`            | Show adapter status and config                                             |
| `/model <id>`        | Override the model for subsequent turns                                    |
| `/model list`        | List available models from the Codex instance                              |
| `/reasoning <level>` | Set reasoning effort (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`) |
| `/help`              | Show all available commands                                                |

---

## Execution Reporting

The adapter reports into the room by default. `emit` is opt-out: omit it and you get everything `CodexAdapter` supports, which is `Emit.TOOL_CALLS`, `Emit.THOUGHTS`, `Emit.TASK_EVENTS`, and `Emit.USAGE`. Pass `emit` to narrow that set:

```python
from band import Emit
from band.adapters import CodexAdapter, CodexAdapterConfig

adapter = CodexAdapter(
    config=CodexAdapterConfig(transport="stdio"),
    emit={Emit.TOOL_CALLS, Emit.THOUGHTS, Emit.TASK_EVENTS},
)
```

`Emit.TOOL_CALLS` reports tool calls and results; `Emit.THOUGHTS` reports Codex reasoning. With both in the set, the adapter sends:

* `thought` events showing Codex's reasoning process
* `tool_call` events when a tool is invoked
* `tool_result` events when a tool returns

`emit=()` silences the adapter entirely. Read the warning below before reaching for it.

> **Warning**
>
> `Emit.TASK_EVENTS` is load-bearing, not just narration: the room's Codex thread ID is persisted in task-event metadata and read back to resume the thread. It is in the default set, so leaving `emit` alone is safe. An explicit `emit=` replaces that default wholesale, so any set you pass must still include `Emit.TASK_EVENTS`, or every restart starts a fresh Codex thread instead of resuming.

---

## Complete Example

Here's a full example with reasoning control, custom instructions, and execution reporting:

**`agent.py`**

```python title="agent.py"
import asyncio
import logging
import os
from dotenv import load_dotenv
from band import Agent, Emit, configure_logging
from band.adapters import CodexAdapter, CodexAdapterConfig
from band.config import load_agent_config

logger = logging.getLogger(__name__)

async def main():
    load_dotenv()
    configure_logging(root_level="INFO")
    agent_id, api_key = load_agent_config("my_agent")

    adapter = CodexAdapter(
        config=CodexAdapterConfig(
            transport="stdio",
            personality="pragmatic",
            model="gpt-5.3-codex",
            cwd=os.getcwd(),
            custom_section="""
            You are a senior Python developer. When users ask questions:
            1. Think through the problem carefully
            2. Provide clear, step-by-step explanations
            3. Include code examples when relevant
            4. Suggest tests for any code changes
            """,
            reasoning_effort="high",
            reasoning_summary="concise",
            approval_mode="manual",
        ),
        emit={Emit.TOOL_CALLS, Emit.TASK_EVENTS},
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket"),
        rest_url=os.getenv("BAND_REST_URL", "https://app.band.ai"),
    )

    logger.info("Codex agent is running! Press Ctrl+C to stop.")
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Debug Mode

If your agent isn't responding as expected, enable debug logging:

**`agent_debug.py`**

```python title="agent_debug.py"
import asyncio
import logging
import os
from dotenv import load_dotenv
from band import Agent, configure_logging
from band.adapters import CodexAdapter, CodexAdapterConfig
from band.config import load_agent_config

logger = logging.getLogger(__name__)

async def main():
    load_dotenv()
    # Enable debug logging for the SDK
    configure_logging(level="DEBUG", root_level="INFO")
    agent_id, api_key = load_agent_config("my_agent")

    adapter = CodexAdapter(
        config=CodexAdapterConfig(
            transport="stdio",
        )
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket"),
        rest_url=os.getenv("BAND_REST_URL", "https://app.band.ai"),
    )

    logger.info("Agent running with DEBUG logging. Press Ctrl+C to stop.")
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
```

With debug logging enabled, you'll see detailed output including:

* JSON-RPC message exchange with Codex
* Thread creation and resume events
* Tool call dispatch and results
* Model discovery and fallback attempts
* Streaming response content

---

## Architecture Notes

The Codex adapter is architecturally different from other adapters:

**JSON-RPC Protocol:**

* Communicates with Codex via bidirectional JSON-RPC 2.0
* Supports both requests (with responses) and notifications (fire-and-forget)
* Automatic retry with exponential backoff on overload errors

**Thread Management:**

* Each chat room maps to a Codex thread
* Thread IDs are persisted in platform task event metadata
* On reconnect, the adapter resumes existing threads for conversation continuity
* Falls back to injecting raw message history if thread resume fails

**Transport Details:**

* **Stdio**: Spawns `codex app-server --listen stdio://` as a subprocess, communicates via stdin/stdout
* **WebSocket**: Connects to a running Codex app server at the configured URL (default `ws://127.0.0.1:8765`)

---

## When to Use Codex vs Claude SDK

| Feature             | Codex                           | Claude SDK               |
| ------------------- | ------------------------------- | ------------------------ |
| Provider            | OpenAI Codex CLI                | Anthropic                |
| Transport           | JSON-RPC (stdio/WebSocket)      | MCP                      |
| Authentication      | `codex login` (local)           | `ANTHROPIC_API_KEY`      |
| Reasoning Control   | effort + summary levels         | Extended thinking tokens |
| Approval System     | Yes (manual/auto)               | No                       |
| Model Discovery     | Automatic via `model/list`      | Explicit                 |
| Session Persistence | Thread IDs in platform metadata | In-memory per room       |
| Sandbox Support     | Configurable sandbox policy     | None                     |

**Use Codex when:**

* You want to use OpenAI models via Codex with your existing setup
* You want fine-grained reasoning and approval control
* You need sandbox isolation for code execution

**Use Claude SDK when:**

* You want to use Anthropic Claude models
* You need extended thinking with visible chain-of-thought
* You want MCP-based tool integration
* You prefer session-based conversation management

---

## Docker Deployment

Run Codex agents with Docker using YAML configuration, no Python code required.

### Quick Start

### Configure environment

From the **repository root**, copy the example environment file and add your OpenAI API key (OpenAI Platform):

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Create agent configuration

Navigate to the Docker example directory and create your agent config:

```bash
cd examples/codex
cp example_agent.yaml agent1.yaml
```

Edit `agent1.yaml` with your agent credentials from the [Band Dashboard](https://app.band.ai/dashboard):

```yaml
agent_id: "agt_abc123xyz"  # Your Agent ID
api_key: "sk_live_..."     # Your API Key

model: gpt-5.3-codex

prompt: |
  You are a helpful coding assistant.
  Be concise and pragmatic.

# Optional: reasoning control
# reasoning_effort: high
# reasoning_summary: concise

# Optional: approval mode
# approval_mode: manual
```

### Build and run

```bash
docker compose build
docker compose up
```

### Environment Variables

The `CODEX_`-prefixed variables `CodexAdapterConfig` already reads work here too, with the defaults the Docker example sets. `CODEX_ROLE` is specific to the Docker runner:

| Variable                 | Default            | Description                           |
| ------------------------ | ------------------ | ------------------------------------- |
| `CODEX_TRANSPORT`        | `stdio`            | Transport mode (`stdio` or `ws`)      |
| `CODEX_CWD`              | `/workspace/repo`  | Working directory for Codex           |
| `CODEX_MODEL`            | auto               | Model ID override                     |
| `CODEX_SANDBOX`          | `external-sandbox` | Sandbox mode                          |
| `CODEX_REASONING_EFFORT` | —                  | Reasoning effort level                |
| `CODEX_APPROVAL_MODE`    | `manual`           | Approval handling mode                |
| `CODEX_ROLE`             | —                  | Loads prompt from `prompts/{role}.md` |

> **Note**
>
> The Docker container mounts `~/.codex` from the host for authentication. Your local `codex login` credentials are shared with the container automatically.

---

## Next Steps

#### [Custom Adapters](/integrations/sdks/tutorials/creating-framework-integrations)

Build adapters for any LLM framework

#### [Reference](/integrations/sdks/reference)

Complete API reference and configuration