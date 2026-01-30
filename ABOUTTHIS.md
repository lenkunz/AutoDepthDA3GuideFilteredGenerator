# Why this was built

This project solves the most common frustrations when using high-end AI depth maps in image viewers.

### 1. The "Brittle Patch" Problem
Changing game code directly (DLL patches) is dangerous and breaks every time the game updates. This tool mimics the game's language from the outside, meaning it keeps working regardless of game updates.

### 2. The 5GB Data Burden
Most AI tools force you to download the same 5GB of "PyTorch" libraries over and over. This tool is a detective—it reuses the libraries already sitting in your game folder, saving you gigabytes of disk space.

### 3. The "Black Box" Workflow
Standard background processes give you zero feedback. If you process 100 images, you're stuck guessing when it will finish. Our terminal dashboard shows you exactly how many seconds are left (ETC).

### 4. Custom Integration (Webhooks)
For advanced users, you can now trigger other tools automatically. When a depth map is finished, we can shoot a "Webhook" to any URL with the image metadata, allowing you to link your own scripts.
