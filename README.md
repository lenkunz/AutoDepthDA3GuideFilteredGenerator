# AutoDepth DA3 Standalone Service

This service acts as a transparent "emulator" for the native depth engine. It allows you to use **Depth Anything V3** without modifying any game code.

## Purpose
The goal is to provide a zero-patch integration by mimicking the game's file-based communication protocol. It monitors for requests and generates depth maps that any compatible mod can read instantly.

## Quick Start
1. Copy this `midas3` folder into your game root.
2. Run `Run_Service.bat` and follow the on-screen setup prompts.
3. In-game, set the Depth Model to **Manual**.

## Logic
- **Input**: Watches `input/` for text requests from the game.
- **Output**: Writes V3 depth maps as `.pfm` files to `output/`.
- **Optimization**: Reuses existing game libraries (Yanking) to save disk space.
