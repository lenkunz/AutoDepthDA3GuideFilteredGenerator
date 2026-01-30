# Depth Anything V3 Standalone Service

This bundle provides a standalone environment for managing and running **Depth Anything V3** requests for your image viewing experience.

## Functional Additions
This implementation focuses on providing more control and visibility over your depth generation workflow:

- **Interactive Dashboard**: Provides a real-time TUI (Terminal User Interface) that shows batch processing status, generation speed, and a precise **ETC** (Estimated Time of Completion).
- **Flexible Configuration**: Allows you to choose between different model variants (Small to Giant) and resolutions on-the-fly to suit your hardware.
- **Dependency Sharing**: Uses a "Yanking" logic to reuse core AI libraries already found on your system, reducing the need for redundant multi-gigabyte downloads.
- **Standalone Execution**: Runs as a separate process in the background, allowing for easier monitoring and troubleshooting without modifying core game files.

## Usage
1. Copy the `midas3` folder into your game root.
2. Run `Run_Service.bat` and follow the setup prompts.
3. In-game, set the Depth Model to **Manual**.
