# Depth Anything V3 Wrapper: Simplified Instructions

## How to run
1. Copy this `midas3` folder into your game root.
2. In-game, set the Depth Model to **Manual**.
3. Run `Run_Service.bat`.

## Webhook 
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
