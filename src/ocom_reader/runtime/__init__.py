"""Deliberately re-exports nothing at package level.

`context.py` and `pipeline.py` depend on `agent/registry.py`, which
(as of Registry Search Integration) depends on
`runtime.query`/`runtime.search` — eagerly importing `RuntimeContext`/
`ingest_document`/`ask` here would force Python to fully initialize
this package before `agent.registry` finishes importing it, producing
a circular import. Nothing in this codebase imports from the bare
`ocom_reader.runtime` package (checked); everything already imports
the specific submodule it needs
(`ocom_reader.runtime.context`, `ocom_reader.runtime.pipeline`,
`ocom_reader.runtime.query.normalizer`, `ocom_reader.runtime.search.policy`).
Keep it that way rather than reintroducing this file as a re-export.
"""
