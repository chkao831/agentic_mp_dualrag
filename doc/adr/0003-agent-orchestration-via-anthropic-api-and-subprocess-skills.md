# ADR-0003: Agent orchestration via Anthropic API and subprocess skills

## Issue

The backend must run a **tool-using LLM** that calls retrieval code safely and transparently. We need to pick an orchestration style **now**: a third-party agent framework, a custom loop on the vendor SDK, and whether tools run **in-process** or **out-of-process**. This choice affects debuggability, security, staffing, and **NFR-03** / **FR-04**.

## Decision

Implement a **custom** control loop with the **Anthropic Python SDK**: repeated `messages.create` calls with tool definitions until the model stops requesting tools. On each `tool_use`, execute an **allowlisted** script under `skills/<skill_name>/` using **`subprocess`**, passing only **structured CLI arguments** derived from validated tool input; append stdout to the conversation as `tool_result` and continue.

## Status

Approved

## Group

Integration; Security (execution boundary)

## Assumptions

- **Anthropic** remains the primary model provider for this phase; SDK stability is acceptable.
- Tool count is **small**; maintaining an allowlist in code is tractable.
- Subprocess startup cost is **acceptable** versus security and isolation benefits for this workload.
- Skill authors can adhere to a **stdout contract** consumable by the model.

## Constraints

- New tools **must** be registered in code (allowlist + schema); ad-hoc script execution from model text is **forbidden** (**NFR-04**).
- `subprocess` calls need **timeouts** and bounded output handling as tools grow.

## Positions

1. **Anthropic SDK + subprocess allowlist (selected):** Explicit loop; tools are separate processes.
2. **Agent framework (e.g. LangGraph, CrewAI):** Faster feature scaffolding; harder to trace control flow and introduces dependency churn.
3. **In-process Python functions:** Lowest latency; larger blast radius if tool code or model-influenced data handling is flawed.
4. **Remote tool server (gRPC/HTTP):** Good for scale-out; adds deployment complexity premature for local-first milestone.

## Argument

An explicit SDK loop satisfies **NFR-03** (maintainability, debuggability) and **FR-04** (autonomous execution with clear boundaries). Subprocess isolation supports **NFR-04** with minimal custom security engineering compared to in-process execution. Frameworks trade **time-to-first-demo** for **long-term comprehension** cost—acceptable for experiments, less so for a small codebase meant to be auditable. Remote servers are deferred until scale demands them.

## Implications

- Onboarding docs must state how to **add a skill** (schema, allowlist, script path).
- Observability should log tool names, durations, and non-sensitive args (**NFR-06**).
- Future ADR may introduce **in-process** tools for hot paths if latency becomes dominant—would need revised threat model.

## Related decisions

- [ADR-0005](0005-streaming-ui-with-sse-and-streamlit.md) — UI consumes SSE that reflects tool steps.
- [ADR-0004](0004-defer-rdf-graph-skill.md) — Fewer live tools while graph skill is off.

## Related requirements

- **FR-04** — Subprocess execution of allowlisted tools on `tool_use`.
- **NFR-03** — Maintainable explicit orchestration on Anthropic SDK.
- **NFR-04** — Restricted execution surface.
- **NFR-06** — Minimum observability at tool boundaries.

## Related artifacts

- `backend/agent.py`
- `backend/main.py`
- `skills/*/SKILL.md`, `skills/*/*.py`
- [`doc/requirements.md`](../requirements.md)

## Related principles

- **Least privilege** for model-driven execution (informal security principle).

## Notes

- Parsing `SKILL.md` metadata into tool schemas automatically is a **future** improvement; schemas currently live in code next to the allowlist.
