# DA3 Service Optimizer

This service provides an optimized, standalone environment for managing and running your **Depth Anything V3** requests.

## What makes this different?
While you may already be using Depth Anything, this specific implementation is designed to streamline your workflow and save resources:

- **Dedicated Workflow Dashboard**: Unlike the native background process, this provides a clear interactive dashboard for batch processing. You get real-time feedback on progress, generation speed, and a precise **ETC** (Estimated Time of Completion).
- **Resource Efficiency**: It intelligently shares system libraries to avoid redundant 5GB+ downloads, keeping your installation lean and fast.
- **Isolated Stability**: By running as a standalone service, it ensures that your depth generation remains stable and doesn't conflict with other game processes.
- **Interactive Control**: Choose between different model sizes and resolutions on-the-fly to match your hardware's VRAM capacity.

## Integration
This tool acts as a transparent bridge. It catches requests and fulfills them using an optimized DA3 engine, allowing for a "zero-patch" experience where you can upgrade or swap models without modifying core game files.

## Quick Start
1. Copy the `midas3` folder into your game root.
2. Run `Run_Service.bat`.
3. In-game, set the Depth Model to **Manual**.
