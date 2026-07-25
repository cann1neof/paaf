# SPDX-License-Identifier: Apache-2.0
"""Adapter-package marker (empty in Phase 2).

Phase 3 adds the LangChain/LangGraph adapter inside this `paaf_llm._engine`
subpackage. It is the ONE place framework imports are permitted: the import-linter
`forbidden` contract (FOUND-04, wired in Plan 02) whitelists exactly this subpackage
via `ignore_imports = ["paaf_llm._engine.* -> langchain*"]`. Keeping the marker here
now makes that future exception target real from the first commit.
"""
