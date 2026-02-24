---
name: web-fetch
description: Fetch one or more URLs via Jina AI Reader (concise stdout + /tmp outputs).
---

# web-fetch

Env: `JINA_AI_KEY`.

Inputs:
- Positional `urls`: one or more URLs.
- `--out-dir` (required): a unique output directory under `/tmp` that does not already exist.

Behavior contract:
- The command fails if `--out-dir` is missing, not under `/tmp`, or already exists.
- The command creates `--out-dir` and writes run outputs into it.
- The command prints run metadata directly to stdout.

Outputs:
- Stdout JSON includes run metadata, success/error counts, and per-URL rows.
- Each per-URL row includes status metadata and content file path when fetch succeeds.

Reading guidance:
- For large content files, read in chunks with `sed` (for example: `sed -n '1,200p' <path>`) instead of printing the whole file at once.

```bash
# Multiple URLs
~/.kapybara/skills/core/web-fetch/fetch \
  https://url1.com https://url2.com \
  --out-dir /tmp/web_fetch_20260224_02
```

Use stdout as the source of run metadata.
