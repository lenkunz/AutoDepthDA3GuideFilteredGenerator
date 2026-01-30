# About Global Depth V3 Service

This service enables **Depth Anything V3** (the latest state-of-the-art AI) for your 3D experience. 

## The Difference: V3 Service vs. Native Engine
What makes this implementation different from the developer’s built-in engine?

1. **State-of-the-Art Engine (V3)**: The native game uses older depth models that can look "jelly-like" or blurry. This service uses **Depth Anything V3**, which provides surgical precision on fine edges (hair, leaves) and rock-solid stability in 3D space.
2. **Transparent "Emulator" Design**: Instead of being a closed "black box" inside the game, this is a separate service. It mimics the game's internal language to catch requests and fulfill them with higher quality—no game code patches required.
3. **Smart "Yanking" Optimization**: Unlike standard AI apps that force 5GB+ downloads, our launcher acts like a detective. it finds and reuses ("yanks") massive AI libraries already installed in your game folders, keeping the setup lightweight and fast.
4. **Real-Time Feedback**: For the first time, you get a clear dashboard during batch generation. You can see your progress, your current speed, and a precise **ETC (Estimated Time of Completion)** which the native engine doesn't show.

## Visual Advantages
- **Ultra-Sharp Details**: Fine details are captured with high precision.
- **Perfect Stability**: Removes the "pulsing" artifacts seen in older models.
- **True Background Depth**: Landscapes have a correct, immersive 3D sense of scale.

## Usage
1. Copy the `midas3` folder into your game root.
2. Run `Run_Service.bat`.
3. In-game, set the Depth Model to **Manual**.
