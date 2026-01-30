# Depth Anything V3 Accelerator

This service provides a depth estimation pipeline optimized for high visual fidelity and VRAM efficiency in VR.

## Performance & Technical Data
This service uses **In-Situ Benchmarking** to provide factual data specific to your hardware. 

- **Full Transparency**: At startup, the service detects your **Current Available VRAM**. This reflects the memory left while your game is already running.
- **Automated Benchmark**: After you select a model, the service runs a 3-pass dry run on your GPU. It explicitly reports:
    - **Actual Peak VRAM** used by the selected configuration.
    - **Average Inference Speed** (ms) on your specific card.
- **Guided Upscaling**: High-resolution detail is achieved via a **Guided Filter**, which upscales depth using your original image as a spatial map without the VRAM cost of native high-res inference.

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


