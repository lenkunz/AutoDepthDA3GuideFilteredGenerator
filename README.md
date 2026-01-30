# Depth Anything V3 Wrapper: Simplified Instructions

## Why this exists
- **No More Broken Patches**: Runs alongside the game. Mod updates won't break it.
- **No More 5GB Downloads**: Reuses the AI libraries already in your game folders.
- **No More Black Boxes**: Shows you exactly how many seconds are left in a batch.

## How to run
1. Copy this `midas3` folder into your game root.
2. Run `Run_Service.bat`.
3. In-game, set the Depth Model to **Manual**.

## Webhook Support
If you want to trigger other tools, add a `webhook_url` to `config.json`.

**Example Payload (POST):**
```json
{
  "event": "depth_generated",
  "input_image": "C:\\Games\\AutoDepth\\input\\photo.jpg",
  "output_depth": "C:\\Games\\AutoDepth\\output\\photo.pfm",
  "model": "da3-giant",
  "resolution": 1024,
  "duration_s": 0.452,
  "timestamp": 1706631234.567
}
```
