# Depth Anything V3 Accelerator (VRAM-Efficient Fidelity)

This service provides a high-fidelity depth estimation pipeline optimized for VR and limited VRAM environments.

## The Problem: Brute-Force vs. Scientific Fidelity
- **Brute-Force**: Increasing inference resolution (e.g., 1280px+) causes massive VRAM spikes, crashing VR setups.
- **Surface Guessing (Depth+)**: Heuristic smoothing creates fake "dots" and average contours that don't respect the actual image geometry.

## Our Solution: Guided Upscaling
Instead of brute-forcing pixels, we use a **PyTorch Guided Filter**. 
1. We run the state-of-the-art **Giant** or **Mono** models at a manageable resolution (e.g., 518px - 768px).
2. We use the original high-res RGB image as a mathematical guide to upscale the depth map.
3. This "snaps" the depth edges to the actual photographic edges, providing 4K-level detail while keeping VRAM usage low.

## How to run
1. Copy this entire folder into your game root.
2. In-game, set the Depth Model to **Manual**.
3. Run **`Run_DA3.bat`** from inside the copied folder.


