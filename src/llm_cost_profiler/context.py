import contextvars

# Holds the name of the agent/graph step (node) currently executing,
# so that LLM calls made anywhere inside that node - whether tracked via
# profile_llm_call() or a LangChain callback - get attributed to it
# automatically, without threading a step argument through every call site.
current_step: "contextvars.ContextVar[str | None]" = contextvars.ContextVar(
    "llm_cost_profiler_current_step", default=None
)
