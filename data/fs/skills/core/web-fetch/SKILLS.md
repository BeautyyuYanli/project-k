---
name: web-fetch
description: Fetch one or more URLs via Jina AI Reader.
---

## Upstream dependency
- Upstream: Jina AI Reader
- Official docs: https://jina.ai/

# web-fetch

Env: `JINA_AI_KEY`.

Fetch results are stored in a temporary directory to prevent race conditions and allow post-processing.

```bash
# Single URL (saves to random /tmp/web-fetch-XXX/)
./fetch "https://example.com"

# Multiple URLs
./fetch https://url1.com https://url2.com --out-dir /tmp/my-custom-fetch
```

The tool will print the path to the saved content. You should read files from that path.
