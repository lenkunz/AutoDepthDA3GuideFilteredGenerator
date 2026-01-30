# About Global Depth V3 Service

This service enables **Depth Anything V3** (the latest state-of-the-art AI) for your image viewing experience. 

> [!NOTE]
> **Why call it "midas3"?**
> While the engine is powered by **Depth Anything V3**, the folder and launcher use the name `midas3` for 100% compatibility with the game's internal code. Think of it as the "Midas" interface running a "DA3" engine.
The original game models often struggle with complex scenes—creating blurry edges or "jelly-like" distortions in 3D. This implementation replaces that engine with V3 technology to achieve:

- **Ultra-Sharp Details**: Fine edges like hair, foliage, and intricate objects are captured with surgical precision.
- **Perfect Stability**: Removes the "swimming" or "pulsing" artifacts seen in older models for a solid, immersive 3D feeling.
- **True Background Depth**: Objects feel correctly placed in 3D space, preventing the "flattened" look in distant landscapes.

## Zero-Impact "Emulator" Design
We built this to be transparent. It sits in the middle and acts as an "emulator" for the game's native depth engine. Because it mimics the game's own language, you can upgrade your visuals without ever having to patch or modify your core game files.

## Optimization & Monitoring
- **Disk Efficiency**: Smartly reuses (yanks) existing AI libraries from your system to avoid redundant 5GB downloads.
- **Real-Time Tracking**: Provides a clear dashboard during batch processing with precise time estimation (ETC).
