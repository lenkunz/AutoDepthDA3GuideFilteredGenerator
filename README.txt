Depth Anything V3 - Standalone Service
======================================

This is a standalone Python-based depth engine. It allows you to test 
Depth Anything V3 without modifying your core game code.

HOW TO USE:
1. Copy this 'midas3' folder into your game root.
2. Run 'Setup_and_Run_DA3.bat'. 
   - Choose between **Aggressive Yanking** (Shared Libraries) or **Fresh Environment**.
   - Your decision will be saved to `launcher_config.json`.
   - It will launch an **interactive menu** for model and resolution selection.
3. In-game, set the Depth Model to 'Manual'.
   - The game will now stop spawning its own midas3.exe.
   - The game will instead write requests to 'input/' and wait for 'output/'.

WHY THIS WORKS:
The service monitors the 'input/' folder for .txt files, generates a V3 depth map, 
and writes a .pfm to 'output/'. This is the exact communication protocol 
your engine already uses, ensuring 100% compatibility with zero code changes.

NOTES:
- First run will download the DA3 models (~2.5GB) from HuggingFace.
- Ensure you have Python 3.10+ installed on your system.
