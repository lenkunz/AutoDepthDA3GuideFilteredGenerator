# AutoDepth Standalone DA3 Service
# ==================================

This bundle provides a standalone Depth Anything V3 service for AutoDepth.

## Installation
1. Copy the `midas3` directory to your game root.
2. Run `Setup_and_Run_DA3.bat`.
   - Choose **Aggressive Yanking** to reuse game libraries (fastest).
   - Choose **Fresh Environment** if you want a clean, isolated setup.

## Technical Details
- **TUI Menu**: Interactive selection of models and resolutions.
- **Yank Engine**: Reuses the game's massive dependencies to save ~5GB of space.
- **Direct Run**: Automatically works on "stripped" game-bundled Python distributions.

## Developer Notes
- Monitor the `input/` folder for requests.
- Depth maps are generated as `.pfm` files in `output/`.
