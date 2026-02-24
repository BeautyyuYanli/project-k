---
name: web-search
description: Batch web search via Jina Search Foundation (concise stdout + /tmp outputs).
---

# web-search

Env: `JINA_AI_KEY` (required).

Inputs:
- Positional `queries`: multiple search queries (batch input).
- `--out-dir` (required): a unique output directory under `/tmp` that does not already exist.

Behavior contract:
- The command fails if `--out-dir` is missing, not under `/tmp`, or already exists.
- The command creates `--out-dir` and writes per-query result files into it.
- The command prints run metadata and all query results directly to stdout.

Outputs:
- Stdout JSON includes run metadata, query counts, and all result rows.
- Each stdout result row includes `title`, `url`, and a length-bounded `description`.
- Per-query JSON files include compact result fields and paths to full text files when available.

## Examples

```bash
# Multiple queries
~/.kapybara/skills/core/web-search/search \
  "rust async runtime comparison" \
  "httpx asyncclient timeout best practices" \
  --out-dir /tmp/web_search_20260224_02
```

Use stdout as the source of run metadata.
