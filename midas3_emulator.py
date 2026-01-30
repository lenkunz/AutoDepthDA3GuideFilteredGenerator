import sys
import os
import argparse
import torch
import numpy as np
from PIL import Image
import time
import gc

import json
import urllib.request

# Python version check
if sys.version_info < (3, 10):
    print("[!] Error: Python 3.10 or higher is required.")
    sys.exit(1)

# Add paths for Depth-Anything-3
# We expect to be in a flat bundle or next to the Depth-Anything-3 folder
if getattr(sys, 'frozen', False):
    # Running in a bundle (EXE)
    BASE_PATH = os.path.dirname(sys.executable)
else:
    # Running in normal Python environment
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

DA3_ROOT = os.path.join(BASE_PATH, "Depth-Anything-3", "Depth-Anything")
if not os.path.exists(DA3_ROOT):
    DA3_ROOT = os.path.join(BASE_PATH, "..", "Depth-Anything-3", "Depth-Anything")

sys.path.append(os.path.join(DA3_ROOT, "src"))

try:
    from depth_anything_3.api import DepthAnything3
except ImportError:
    print(f"[!] Error: Could not import depth_anything_3. Ensure 'Depth-Anything-3' is at: {DA3_ROOT}")
    sys.exit(1)

def save_pfm(path, image, scale=-1.0):
    """Saves a 2D numpy array as a PFM file (grayscale)."""
    with open(path, 'wb') as f:
        color = 'Pf\n' 
        f.write(color.encode())
        f.write(f'{image.shape[1]} {image.shape[0]}\n'.encode())
        f.write(f'{scale}\n'.encode())
        image_to_save = np.flipud(image).astype(np.float32)
        f.write(image_to_save.tobytes())

class MidasEmulator:
    def __init__(self, model_name="da3-giant", resolution=1024, vram_reserve=6.0):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.resolution = resolution
        self.vram_reserve = vram_reserve
        self.model = None
        self.model_name = model_name
        self.processing_times = []
        
        # Load Config
        self.config = {}
        self.config_path = os.path.join(BASE_PATH, "config.json")
        self.load_config()

        print(f"[*] Midas DA3 Service Initialization")
        print(f"[*] Device: {self.device}")
        print(f"[*] Memory: Reserving {vram_reserve}GB VRAM.")
        
        self.load_model()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"[!] Error loading config.json: {e}")

    def send_webhook(self, img_path, out_path, duration):
        webhook_url = self.config.get("webhook_url")
        if not webhook_url:
            return

        try:
            payload = {
                "event": "depth_generated",
                "input_image": os.path.abspath(img_path),
                "output_depth": os.path.abspath(out_path),
                "model": self.model_name,
                "resolution": self.resolution,
                "duration_s": round(duration, 3),
                "timestamp": time.time()
            }
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response:
                pass 
        except Exception as e:
            print(f"[!] Webhook error: {e}")

    def load_model(self):
        print(f"[*] Initializing model {self.model_name}... (Will auto-download if missing)")
        try:
            # DepthAnything3.from_pretrained handles auto-downloading from HuggingFace
            self.model = DepthAnything3.from_pretrained("depth-anything/" + self.model_name).to(self.device)
            self.model.eval()
            print("[+] Model ready.")
        except Exception as e:
            print(f"[!] Model initialization failed: {e}")
            print("[*] Tip: Ensure you have an active internet connection for the first run.")
            sys.exit(1)

    def process_image(self, img_path, out_path, silent=False):
        try:
            if not silent: print(f"[*] Processing: {os.path.basename(img_path)}")
            
            # Pre-flight VRAM cleanup (Low Profile)
            if self.device == "cuda":
                torch.cuda.empty_cache()
                gc.collect()
                
                # Check global memory
                free_vram, _ = torch.cuda.mem_get_info(0)
                if (free_vram / (1024**3)) < self.vram_reserve:
                    if not silent: print(f"[!] Waiting for VRAM... (Current Free: {free_vram/(1024**3):.1f}GB)")
                    # Small wait if VRAM is very tight
                    time.sleep(0.5)

            # Load and inference
            img_pil = Image.open(img_path).convert("RGB")
            img_np = np.array(img_pil)
            
            with torch.no_grad():
                with torch.autocast(device_type=self.device, dtype=torch.float16 if self.device == "cuda" else torch.float32):
                    prediction = self.model.inference([img_np], process_res=self.resolution)
            
            depth = prediction.depth[0]
            if hasattr(depth, 'cpu'): depth = depth.cpu().numpy()
            
            # MinMax Normalization (Standard for AutoDepthMod .pfm)
            d_min, d_max = depth.min(), depth.max()
            depth_norm = (depth - d_min) / (d_max - d_min + 1e-8)
            
            save_pfm(out_path, depth_norm)
            if not silent: print(f"[+] Done -> {os.path.basename(out_path)}")
            
            # Post-flight cleanup
            del prediction; del depth; del img_np
            if self.device == "cuda":
                torch.cuda.empty_cache()
                gc.collect()

        except Exception as e:
            print(f"[!] Processing Error: {e}")

    def watch_mode(self, input_dir, output_dir):
        print(f"[*] WATCH MODE ACTIVE. Monitoring: {input_dir}")
        processed_mtimes = {}
        session_processed = 0
        session_start_time = 0

        while True:
            try:
                if not os.path.exists(input_dir):
                    time.sleep(1)
                    continue

                # Scan for all .txt requests
                txt_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.txt')]
                
                # Identify pending files
                pending = []
                for f in txt_files:
                    txt_path = os.path.join(input_dir, f)
                    mtime = os.path.getmtime(txt_path)
                    if f not in processed_mtimes or processed_mtimes[f] < mtime:
                        pending.append((f, txt_path, mtime))
                
                if not pending:
                    if session_processed > 0:
                        duration = time.time() - session_start_time
                        print(f"[*] Batch finished. Processed {session_processed} files in {duration:.1f}s")
                    session_processed = 0
                    time.sleep(0.2)
                    continue

                if session_processed == 0:
                    session_start_time = time.time()
                    print(f"[*] New batch detected: {len(pending)} files.")

                total_in_batch = session_processed + len(pending)
                
                for f_name, f_path, mtime in pending:
                    try:
                        with open(f_path, 'r', encoding='utf-8') as tf:
                            img_path = tf.read().strip().strip('"')
                        
                        if os.path.exists(img_path):
                            out_name = os.path.splitext(f_name)[0] + ".pfm"
                            out_path = os.path.join(output_dir, out_name)
                            
                            start_t = time.time()
                            self.process_image(img_path, out_path, silent=True)
                            end_t = time.time()
                            
                            duration = end_t - start_t
                            self.send_webhook(img_path, out_path, duration)
                            
                            # Update stats
                            duration = end_t - start_t
                            self.processing_times.append(duration)
                            if len(self.processing_times) > 10: self.processing_times.pop(0)
                            
                            session_processed += 1
                            avg = sum(self.processing_times) / len(self.processing_times)
                            remaining = total_in_batch - session_processed
                            etc = remaining * avg
                            percent = int((session_processed / total_in_batch) * 100)
                            
                            print(f"[Batch: {session_processed}/{total_in_batch}] [{percent:3d}%] "
                                  f"ETC: {etc:4.1f}s | Speed: {avg:4.2f}s/img | {f_name}")
                            
                        processed_mtimes[f_name] = mtime
                    except Exception as e:
                        print(f"[!] Error processing {f_name}: {e}")
                
                # Cleanup processed_mtimes cache
                if len(processed_mtimes) > 500:
                    processed_mtimes = {k: v for k, v in processed_mtimes.items() if k in txt_files}

                time.sleep(0.1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[!] Watch error: {e}")
                time.sleep(1)

def show_menu():
    print("""
    ========================================
     Depth Anything V3 - Model Selection
    ========================================
    [1] DA3-Giant      (Highest Quality / ~2.5GB)
    [2] DA3-Mono-Large (Very High / ~1.3GB)
    [3] DA3-Large      (High Quality/ ~1.3GB)
    [4] DA3-Base       (Balanced / ~360MB)
    [5] DA3-Small      (Fast / ~100MB)
    ========================================
    """)
    m_choice = input("Select Model [1-5]: ").strip()
    m_mapping = {
        "1": "da3-giant",
        "2": "da3mono-large",
        "3": "da3-large",
        "4": "da3-base",
        "5": "da3-small"
    }
    model = m_mapping.get(m_choice, "da3-giant")

    print("""
    ========================================
     Inference Resolution Selection
    ========================================
    [1] 518  - Low Profile (Fast / Lowest VRAM)
    [2] 768  - Balanced    (Good for most GPUs)
    [3] 1024 - HD Detail   (Recommended / Standard)
    [4] 1280 - Ultra       (High Quality / ~8GB+ VRAM)
    [5] 1512 - Extreme     (Max Detail / 12GB+ VRAM)
    ========================================
    """)
    r_choice = input("Select Resolution [1-5]: ").strip()
    r_mapping = {
        "1": 518,
        "2": 768,
        "3": 1024,
        "4": 1280,
        "5": 1512
    }
    res = r_mapping.get(r_choice, 1024)
    
    return model, res

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Midas DA3 Service")
    parser.add_argument("--model_type", type=str, help="Target model (e.g. da3-giant)")
    parser.add_argument("--input_path", type=str, default="input", help="Input directory")
    parser.add_argument("--output_path", type=str, default="output", help="Output directory")
    parser.add_argument("--continuous", action="store_true", help="Enable watch mode")
    parser.add_argument("--height", type=int, help="Resolution (Inference Size)")
    parser.add_argument("--delete", action="store_true", help="Ignored")
    parser.add_argument("--optimize", action="store_true", help="Ignored")
    
    args = parser.parse_args()

    # Ensure directories exist
    os.makedirs(args.input_path, exist_ok=True)
    os.makedirs(args.output_path, exist_ok=True)

    # TUI Model/Res Selection if not forced by CLI
    target_model = args.model_type
    target_res = args.height

    if not target_model or not target_res:
        t_model, t_res = show_menu()
        if not target_model: target_model = t_model
        if not target_res: target_res = t_res
        print(f"[*] Config: {target_model} @ {target_res}px")
        time.sleep(0.5)

    # Technical Mapping for Game Requests (Backward Compatibility)
    technical_mapping = {
        "depth_pro": "da3-giant",
        "DA3o_large": "da3mono-large",
        "DADo_large": "da3-giant",
        "DAD_large": "da3-giant"
    }
    if target_model in technical_mapping:
        print(f"[*] Technical request '{target_model}' -> Using {technical_mapping[target_model]}")
        target_model = technical_mapping[target_model]

    emulator = MidasEmulator(model_name=target_model, resolution=target_res)
    
    if args.continuous:
        emulator.watch_mode(args.input_path, args.output_path)
    else:
        print("[!] Standalone single-file processing not implemented in CLI (Use --continuous).")
