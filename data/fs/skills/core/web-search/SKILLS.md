---
name: web-search
description: Web search via Jina Search Foundation (JSON output).
---

## Upstream dependency
- Upstream: Jina AI Search Foundation
- Official docs: https://docs.jina.ai/

# web-search

Env: `JINA_AI_KEY` (required).

Search results must be dumped to a file in `/tmp` before consumption. Use the provided search script.

```bash
# Search (saves to random /tmp/jina_search_XXX.json)
~/skills/core/web-search/search "your query"

# Search with custom output path
~/skills/core/web-search/search "your query" --out /tmp/my_search.json
```

Always use these files to consume search results instead of parsing direct stdout if the output is large.
