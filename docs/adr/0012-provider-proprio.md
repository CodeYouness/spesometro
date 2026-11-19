# 0012 — `Provider` proprio, una sola strada

**Contesto:** la v1.3 lasciava aperta la scelta tra un'interfaccia `Provider` propria e `init_chat_model` di LangChain.
**Decisione:** interfaccia `Provider` propria in `packages/core`, con implementazioni Anthropic e Mistral sugli SDK ufficiali (entrambi su `httpx2`) e una OpenAI-compatible solo per la colonna dell'eval. Niente LiteLLM, niente `init_chat_model`.
**Conseguenze:** tracce LangSmith con `@traceable` sulle chiamate del Provider; LangChain resta solo per LangGraph.
