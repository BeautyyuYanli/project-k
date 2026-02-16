---
name: web-search
description: Web search via Jina Search Foundation (JSON output).
---

## Upstream dependency
- Upstream: Jina AI Search Foundation
- Official docs: https://docs.jina.ai/

# web-search

Env: `JINA_AI_KEY` (required).

`--out` is required and must point to a unique file path.
The script refuses to overwrite an existing path so concurrent runs do not race.

```bash
# Search
~/skills/core/web-search/search "your query" --out /tmp/jina_search_01.json
```

The output file content is exactly the same as stdout. Always read the output file when stdout may be truncated by tooling.
