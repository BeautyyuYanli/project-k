---
name: restart
description: Check ~/restarting file, toggle it, and restart ~/start.sh if needed.
---

# maintain/restart

This skill manages the restart cycle by toggling the `~/restarting` flag file.

## Usage

```bash
~/skills/maintain/restart/restart.sh
```

- If `~/restarting` does NOT exist: 
    - Creates the file.
    - Kills the running `~/start.sh` process.
- If `~/restarting` DOES exist:
    - Deletes the file.
    - Outputs `already restarted`.
