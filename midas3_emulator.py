import sys
import os
import argparse
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image
import time
import gc

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

class GuidedFilter(torch.nn.Module):
    def __init__(self, r, eps=1e-2):
        super(GuidedFilter, self).__init__()
        self.r = r
        self.eps = eps

    def forward(self, lr_depth, hr_guide):
        # lr_depth: (B, 1, h, w)
        # hr_guide: (B, 3, H, W) 
        
        # Simple box filter via AvgPool
        def box_filter(x, r):
            return torch.nn.functional.avg_pool2d(x, kernel_size=2*r+1, stride=1, padding=r)

        # Upsample LR depth to HR guide size
        B, C, H, W = hr_guide.shape
        p = torch.nn.functional.interpolate(lr_depth, size=(H, W), mode='bilinear', align_corners=False)
        I = hr_guide.mean(dim=1, keepdim=True) # Guidance as grayscale
        
        N = box_filter(torch.ones(B, 1, H, W, device=hr_guide.device), self.r)
        
        mean_I = box_filter(I, self.r) / N
        mean_p = box_filter(p, self.r) / N
        mean_Ip = box_filter(I * p, self.r) / N
        cov_Ip = mean_Ip - mean_I * mean_p
        
        mean_II = box_filter(I * I, self.r) / N
        var_I = mean_II - mean_I * mean_I
        
        a = cov_Ip / (var_I + self.eps)
        b = mean_p - a * mean_I
        
        mean_a = box_filter(a, self.r) / N
        mean_b = box_filter(b, self.r) / N
        
        return mean_a * I + mean_b

class MidasEmulator:
    def __init__(self, model_name="da3-giant", resolution=1024, vram_reserve=6.0):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.resolution = resolution
        self.vram_reserve = vram_reserve
        self.model = None
        self.model_name = model_name
        self.processing_times = []
        
        # Guided Filter (r=8, eps=1e-2 is standard for depth)
        self.gf = GuidedFilter(r=8, eps=1e-2)

        print(f"[*] Midas DA3 Service Initialization")
        print(f"[*] Device: {self.device}")
        print(f"[*] Memory: Reserving {vram_reserve}GB VRAM.")
        
        self.load_model()

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
            orig_w, orig_h = img_pil.size
            img_np = np.array(img_pil)
            
            # Prepare guidance image (normalized)
            img_tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0).to(self.device).float() / 255.0
            
            with torch.no_grad():
                with torch.autocast(device_type=self.device, dtype=torch.float16 if self.device == "cuda" else torch.float32):
                    prediction = self.model.inference([img_np], process_res=self.resolution)
            
            depth = prediction.depth[0] # This is a numpy array (N, H, W) from the API
            
            # Convert to tensor for Guided Filter
            depth_t = torch.from_numpy(depth).unsqueeze(0).unsqueeze(0).to(self.device)
            
            # Apply Guided Upscaling to original image resolution
            depth_hr = self.gf(depth_t, img_tensor)
            
            depth_final = depth_hr.squeeze().cpu().numpy()
            
            # MinMax Normalization
            d_min, d_max = depth_final.min(), depth_final.max()
            depth_norm = (depth_final - d_min) / (d_max - d_min + 1e-8)
            
            save_pfm(out_path, depth_norm)
            if not silent: print(f"[+] Fidelity Upscale ({orig_w}x{orig_h}) -> {os.path.basename(out_path)}")
            
            # Post-flight cleanup
            del prediction; del depth; del depth_t; del depth_hr; del img_tensor; del img_np
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
     Note: Sizes refer to pure model weights.
     
    [1] DA3-Giant (~2.5 GB) - Best Quality
    [2] DA3-Mono-Large (~1.3 GB) - Very High
    [3] DA3-Large (~1.3 GB) - High Quality
    [4] DA3-Base (~360 MB) - Balanced
    [5] DA3-Small (~100 MB) - Fast / Low Profile
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
    
    print("\n[!] IMPORTANT: Set Game 'Depth Model' to MANUAL now.")
    print("[!] Otherwise, the game will ignore this service.\n")
    time.sleep(2)
    
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
    
    # Final Hardware Check / Warning
    if emulator.device == "cpu":
        print("\n" + "!"*40)
        print(" CRITICAL PERFORMANCE WARNING")
        print(" Running on CPU - Expect EXTREME slowness.")
        print(" (30s+ per image, VR will likely lag)")
        print("!"*40 + "\n")
    else:
        try:
            free, total = torch.cuda.mem_get_info()
            print(f"[*] Hardware Status: CUDA Ready | VRAM Free: {free/1024**3:.1f} GB")
        except: pass

    if args.continuous:
        emulator.watch_mode(args.input_path, args.output_path)
    else:
        print("[!] Standalone single-file processing not implemented in CLI (Use --continuous).")
