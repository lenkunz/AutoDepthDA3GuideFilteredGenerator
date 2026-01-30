# AutoDepth DA3 Standalone Service

This service acts as a transparent **Emulator** for the native depth engine, allowing you to use **Depth Anything V3** without complex modding or code changes.

## What is this trying to do?
Instead of forcing you to patch the game, this tool mimics the way the game already talks to its background processes. It "sits in the middle," catching depth requests and fulfilling them using high-quality V3 models.

## Key Advantages
- **Zero-Patch**: Works instantly with any mod that supports the standard communication protocol.
- **Save Disk Space**: Smartly reuses (yanks) existing AI libraries already present on your system, avoiding redundant 5GB+ downloads.
- **Visual Feedback**: Provides a clear interface with real-time progress and time estimation for batch processing.

## Quick Start
1. Copy the `midas3` folder into your game root.
2. Run `Run_Service.bat` and follow the on-screen prompts.
3. In-game, set the Depth Model to **Manual**.
