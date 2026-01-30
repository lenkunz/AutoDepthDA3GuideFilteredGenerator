# Depth Anything V3 Accelerator

This service provides a depth estimation pipeline optimized for high visual fidelity and VRAM efficiency in VR.

## Technical Overview
The accelerator utilizes a **Guided Filter** to balance detail and performance.
- **Inference Efficiency**: Depth is estimated at a consistent resolution (e.g., 512px–1024px).
- **Guided Upscaling**: The high-resolution original RGB image is used as a spatial map to upscale the low-resolution depth output. This ensures sharp edges that align with the photographic content without the VRAM cost of native high-resolution inference.

## Performance Benchmarks (Approximate)
Measurements taken on RTX 30-series / 40-series hardware:
| Model Variant | Resolution | VRAM Usage | Processing Time |
| :--- | :--- | :--- | :--- |
| **DA3-Giant** | 512px | ~4.5 GB | 0.4s - 1.2s |
| **DA3-Giant** | 1024px | ~8.5 GB | 1.5s - 2.8s |
| **DA3-Large** | 512px | ~1.8 GB | 0.2s - 0.5s |
| **DA3-Large** | 1024px | ~3.5 GB | 0.6s - 1.2s |

## Aesthetic Options
- **Standard**: Linear depth estimation.
- **Boosted**: Applies a **Gamma power curve** ($depth = depth^{1.25}$) to the output. This increases relative contrast in the mid-to-far ranges. High-contrast areas (edges) remain structurally consistent with the standard output.

## Usage
1. Copy the `midas3` folder to the game's root directory.
2. In-game, set the **Depth Model** to **Manual**.
3. Run **`Run_DA3.bat`** to start the service.

### Hotkeys
- **[R]**: Return to the model/boost selection menu.
- **[Q]** or **[Ctrl+C]**: Clean exit (releases VRAM).


