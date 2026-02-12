---
name: execute-code
description: Runs scripts reproducibly via `uv` PEP 723 scripts (recommended).
---

# execute-code

Ref: https://docs.astral.sh/uv/guides/scripts/

## Recommended format: `uv` shebang + PEP 723
Example: at the very top of `script.py`
```py
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"          # optional
# dependencies = ["requests<3", "rich"]
# ///
```

Create/update the inline dependency block:
```bash
uv add --script script.py 'requests<3' rich
```

## Run
```bash
chmod +x script.py
./script.py
```

## Heredoc example (quick one-off script)
```bash
cat > /tmp/script.py <<'PY'
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests<3"]
# ///

import requests
print(requests.get("https://example.com").status_code)
PY
chmod +x /tmp/script.py
/tmp/script.py
```
