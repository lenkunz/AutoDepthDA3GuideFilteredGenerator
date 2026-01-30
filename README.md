# Depth Anything V3 Accelerator

This service provides a depth estimation pipeline optimized for high visual fidelity and VRAM efficiency in VR.

## Performance & Technical Data
This service uses **In-Situ Benchmarking** to provide factual data specific to your hardware.

- **In-Situ Benchmarking (Optional)**: After selecting a model, you can choose to run a 3-pass dry run.
    - **Measured Stats**: Reports the **Actual Peak VRAM** and **Average Speed** on your specific GPU.
    - **Skip Option**: You can skip this step to save VRAM and start processing immediate game requests.
- **VRAM Transparency**: At startup, the service detects your **Current Available VRAM**. This reflects the memory left while your game is already running.
- **Guided Upscaling (CPU-Bound)**: High-resolution detail is achieved via a **Guided Filter**. This operation is strictly offloaded to the **CPU** to preserve GPU performance for VR rendering.

## Aesthetic Options
- **Standard**: Linear depth estimation.
- **Boosted**: Applies a **Gamma power curve** ($depth = depth^{1.25}$). This increases relative deep-field contrast for a more pronounced 3D effect.

## Usage
1. Copy the `midas3` folder to the game's root directory.
2. In-game, set the **Depth Model** to **Manual**.
3. Run **`Run_DA3.bat`** to start the service.

### Hotkeys
- **[R]**: Return to the model/boost selection menu.
- **[Q]** or **[Ctrl+C]**: Clean exit (releases VRAM).


