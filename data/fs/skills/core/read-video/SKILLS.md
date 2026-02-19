---
name: read-video
description: Extracts video frames at 1 FPS, assembles them into 3x3 grid images, and prints the absolute grid paths. Complement to the read_media tool.
---

# read-video

## Usage

Extracts frames from a video at a rate of 1 frame per second, then assembles every 9 frames into a 3x3 grid image. Only the grid image paths are printed (no individual frames).

**Important Rule**: You **must** call the `read_media` tool on all extracted grid paths immediately after the script finishes.

### Interface

```bash
~/skills/core/read-video/read <video_path>
```

### Behavior

- Processes videos up to **45 minutes** long.
- Outputs the **absolute paths of grid images** (3x3 九宫格) to stdout, one per line. Individual frame paths are NOT output.
- Fails with a non-zero exit code (e.g., code 3 for duration limit) if the video is too long or extraction fails.
