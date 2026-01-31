import sys
import os
import argparse
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image
import time
import gc
import cv2
import shutil
import msvcrt # Windows-specific key detection
import json

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

# --- WEIGHTS REDIRECTION ---
# Ensure models are saved to the Game's Midas3/weights folder
# instead of the user's hidden AppData folder.
WEIGHTS_PATH = os.path.join(BASE_PATH, "weights")
os.makedirs(WEIGHTS_PATH, exist_ok=True)
os.environ["HF_HOME"] = WEIGHTS_PATH
os.environ["HUGGINGFACE_HUB_CACHE"] = WEIGHTS_PATH

sys.path.append(os.path.join(DA3_ROOT, "src"))

try:
    from depth_anything_3.api import DepthAnything3
except ImportError:
    print(f"[!] Error: Could not import depth_anything_3. Ensure 'Depth-Anything-3' is at: {DA3_ROOT}")
    sys.exit(1)

def robust_imread(path, flags=cv2.IMREAD_UNCHANGED):
    """Robustly reads images with Unicode paths on Windows."""
    try:
        data = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(data, flags)
        if img is not None: return img
    except: pass
    try:
        img = cv2.imread(path, flags)
        if img is not None: return img
    except: pass
    if any(ord(c) > 127 for c in path):
        try:
            temp_path = os.path.join(os.environ.get("TEMP", "."), f"da3_tmp_read_{hash(path)}.exr")
            shutil.copy2(path, temp_path)
            img = cv2.imread(temp_path, flags)
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass
            return img
        except: pass
    return None

def robust_imwrite(path, img):
    """Robustly saves images with Unicode paths on Windows."""
    try:
        if not any(ord(c) > 127 for c in path):
            return cv2.imwrite(path, img)
        ext = os.path.splitext(path)[1]
        if ext.lower() in [".exr", ".pfm"]:
            temp_path = os.path.join(os.environ.get("TEMP", "."), f"da3_tmp_write_{hash(path)}{ext}")
            cv2.imwrite(temp_path, img)
            if os.path.exists(path): os.remove(path)
            shutil.move(temp_path, path)
            return True
        else:
            _, data = cv2.imencode(ext, img)
            data.tofile(path)
            return True
    except: return False

def save_pfm(path, image, scale=-1.0):
    """Saves a 2D numpy array as a PFM file (grayscale)."""
    with open(path, 'wb') as f:
        color = 'Pf\n' 
        f.write(color.encode())
        f.write(f'{image.shape[1]} {image.shape[0]}\n'.encode())
        f.write(f'{scale}\n'.encode())
        image_to_save = np.flipud(image).astype(np.float32)
        f.write(image_to_save.tobytes())

def guided_filter_refinement(I, p, r, eps):
    """
    Manual CPU-bound Guided Filter for VR stability.
    I: Guide (Grayscale 0.0-1.0)
    p: Input (Depth 0.0-1.0)
    """
    def box_filter(img, r):
        return cv2.blur(img, (2*r+1, 2*r+1))

    I = I.astype(np.float32)
    p = p.astype(np.float32)

    N = box_filter(np.ones_like(I), r)
    
    mean_I = box_filter(I, r) / N
    mean_p = box_filter(p, r) / N
    mean_Ip = box_filter(I * p, r) / N
    cov_Ip = mean_Ip - mean_I * mean_p
    
    mean_II = box_filter(I * I, r) / N
    var_I = mean_II - mean_I * mean_I
    
    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I
    
    mean_a = box_filter(a, r) / N
    mean_b = box_filter(b, r) / N
    
    return mean_a * I + mean_b

def load_pfm(path):
    """Loads a PFM file into a 2D numpy array."""
    try:
        with open(path, 'rb') as f:
            header = f.readline().decode().strip()
            if header not in ['Pf', 'PF']: return None
            
            dims = f.readline().decode().strip().split()
            if len(dims) != 2: return None
            w, h = map(int, dims)
            
            scale = float(f.readline().decode().strip())
            endian = '<' if scale < 0 else '>'
            
            data = np.fromfile(f, endian + 'f')
            data = np.reshape(data, (h, w))
            data = np.flipud(data)
            return data
    except: return None

class MidasEmulator:
    def __init__(self, model_name="da3-giant", resolution=1024, vram_reserve=6.0, boost=1.0, run_bench=False):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.resolution = resolution
        self.vram_reserve = vram_reserve
        self.boost = boost # Gamma adjustment for depth contrast
        self.run_bench = run_bench
        self.model = None
        self.model_name = model_name
        self.processing_times = []
        
        # Configuration placeholders
        self.cache_local = False
        self.invert = False # Raw Model Output (Disparity: Near = 1.0)
        
        # VRAM status
        self.vram_status = "Ready"

        print(f"[*] Midas Service Ready")
        print(f"[*] Device: {self.device}")

        print(f"[*] Midas DA3 Service Initialization")
        print(f"[*] Device: {self.device}")
        
        self.pending_count = 0
        
        # Report actual free VRAM at start (Internal check, bypasses system path)
        if self.device == "cuda":
            free, total = torch.cuda.mem_get_info()
            print(f"[*] VRAM Status: {free/1024**3:.1f} GB Available / {total/1024**3:.1f} GB Total")
        
        print(f"[*] Memory: Reserving {vram_reserve}GB Safety Margin.")
        
        self.load_model()
        
        # Perform in-situ benchmark if requested
        if self.device == "cuda" and self.run_bench:
            self.run_benchmark()

    def load_model(self):
        print(f"[*] Initializing model {self.model_name}...")
        try:
            repo = "depth-anything/" + self.model_name
            
            # Factual mapping for Depth Anything V2
            v2_map = {
                "v2-giant": "Depth-Anything-V2-Giant",
                "v2-large": "Depth-Anything-V2-Large",
                "v2-base": "Depth-Anything-V2-Base", 
                "v2-small": "Depth-Anything-V2-Small"
            }
            
            if self.model_name in v2_map:
                repo = "depth-anything/" + v2_map[self.model_name]
            
            # Loading via DepthAnything3 API (assuming compatibility or separate repo)
            self.model = DepthAnything3.from_pretrained(repo).to(self.device)
            self.model.eval()
            print("[+] Model ready.")
        except Exception as e:
            print(f"[!] Model initialization failed: {e}")
            print("[*] Tip: Ensure you have an active internet connection for the first run.")
            sys.exit(1)

    def run_benchmark(self):
        """Perform a 3-pass benchmark to get actual hardware stats."""
        print(f"[*] Running 3-pass Benchmark ({self.model_name} @ {self.resolution}px)...")
        dummy_img = np.random.randint(0, 255, (self.resolution, self.resolution, 3), dtype=np.uint8)
        
        # Reset Peak Tracking
        torch.cuda.reset_peak_memory_stats()
        timings = []
        
        try:
            for i in range(3):
                start = time.time()
                with torch.no_grad():
                    with torch.autocast(device_type=self.device, dtype=torch.float16):
                        _ = self.model.inference([dummy_img], process_res=self.resolution)
                timings.append(time.time() - start)
            
            avg_time = sum(timings) / len(timings)
            peak_vram = torch.cuda.max_memory_reserved() / (1024**3)
            
            print(f"[+] BENCHMARK STATS (Actual Hardware):")
            print(f"    - Peak VRAM Usage:  {peak_vram:.2f} GB")
            print(f"    - Avg Inference:    {avg_time*1000:.0f} ms")
            print(f"    - Note: This is your real-world performance baseline.\n")
            
        except Exception as e:
            print(f"[!] Benchmark Failed: {e}")
        finally:
            torch.cuda.empty_cache()
            gc.collect()


    def process_image(self, img_path, out_path, silent=False):
        try:
            # Resolve physical path to ensure cache follows the real file
            real_img_path = os.path.realpath(img_path)
            
            if not silent:
                print(f"[*] Processing: {os.path.basename(img_path)} ({self.resolution}px)")
                if real_img_path != img_path:
                    print(f"    - Resolved: {real_img_path}")
            
            # Pre-flight VRAM cleanup (Low Profile)
            if self.device == "cuda":
                torch.cuda.empty_cache()
                gc.collect()
                
                # Check global memory
                free_vram, _ = torch.cuda.mem_get_info(0)
                if (free_vram / (1024**3)) < self.vram_reserve:
                    time.sleep(0.5)

            # Load and inference
            img_pil = Image.open(img_path).convert("RGB")
            orig_w, orig_h = img_pil.size
            img_np = np.array(img_pil)
            
            with torch.no_grad():
                with torch.autocast(device_type=self.device, dtype=torch.float16 if self.device == "cuda" else torch.float32):
                    prediction = self.model.inference([img_np], process_res=self.resolution)
            
            depth = prediction.depth[0]
            # Normalize immediately on CPU for upscaling stage
            d_min, d_max = depth.min(), depth.max()
            depth_inf = ((depth - d_min) / (d_max - d_min + 1e-8)).astype(np.float32)
            

            # CPU Guided Filter Refinement
            guide = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
            depth_high = cv2.resize(depth_inf, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
            depth_final = guided_filter_refinement(guide, depth_high, r=8, eps=1e-3)
            
            # --- FINAL PROCESSING: FLIP & BOOST ---
            # Standardized: Python creates "Game Ready" data (0.0 = Near)
            # We use the raw depth_final (which has AI's relative scale)
            # and flip it within its own range.
            d_min_f, d_max_f = depth_final.min(), depth_final.max()
            
            # --- FINAL PROCESSING: FLIP & NORMALIZATION ---
            # Standardized: Python creates "Game Ready" data (0.0 = Near) 
            # We normalize to 0-1 for consistent thickness in the image viewer.
            d_min_f, d_max_f = depth_final.min(), depth_final.max()
            d_range_f = d_max_f - d_min_f + 1e-8
            depth_final = (depth_final - d_min_f) / d_range_f
            
            # Since AI output is Disparity (1.0 = Near), we flip to Metric-like (0.0 = Near)
            if hasattr(self, 'invert') and self.invert:
                depth_final = 1.0 - depth_final 
            
            # --- VANILLA COMPATIBILITY (SCALE COUNTER) ---
            # The original game divides depth by the model's MaxDepth.
            # Applying a power curve (Gamma) for pop
            if hasattr(self, 'boost') and self.boost != 1.0:
                depth_final = np.power(depth_final, self.boost)

            # --- LOCAL CACHE (Save next to original image) ---
            # Standard: Local cache is ALWAYS 0-1 normalized for portability.
            if hasattr(self, 'cache_local') and self.cache_local:
                try:
                    cache_name = f"{os.path.basename(real_img_path)}.{self.resolution}.f16.depth"
                    cache_path = os.path.join(os.path.dirname(real_img_path), cache_name)
                    depth_final.astype(np.float16).tofile(cache_path)
                except Exception as cache_err:
                    pass

            # --- VANILLA COMPATIBILITY (SCALE COUNTER) ---
            # The original game divides depth by the model's MaxDepth.
            # We put the "Vanilla Scale" into the PFM header so the pixels stay 0-1
            # (High precision) but the game sees the intended thickness.
            compatibility_map = {
                "da3-giant": 6.0,
                "v2-large": 240.0,
                "v2-base": 24.0,
                "v2-small": 12.0,
                "da2-giant": 600.0
            }
            v_scale = compatibility_map.get(self.model_name.lower(), 1.0)
            
            # Use negative sign for Little-Endian (Standard PFM)
            pfm_header_scale = -v_scale if (hasattr(self, 'vanilla_compat') and self.vanilla_compat) else -1.0

            save_pfm(out_path, depth_final, scale=pfm_header_scale)
            if not silent: 
                v_msg = f" (Vanilla Header x{v_scale})" if (pfm_header_scale != -1.0) else " (Normalized 0-1)"
                print(f"    - Done: {os.path.basename(out_path)}{v_msg}")

            # Post-flight cleanup
            del prediction; del depth; del depth_final; del img_np
            if self.device == "cuda":
                torch.cuda.empty_cache()
                gc.collect()

        except Exception as e:
            print(f"[!] Processing Error: {e}")

    def watch_mode(self, input_dir, output_dir):
        print(f"[*] WATCH MODE ACTIVE. Monitoring: {input_dir}")
        print("[*] HOTKEYS: [R] Reselect Model | [Q] Quit Cleanly")
        processed_mtimes = {}

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
                    time.sleep(0.2)
                    continue

                
                for f_name, f_path, mtime in pending:
                    try:
                        with open(f_path, 'r', encoding='utf-8') as tf:
                            img_path = tf.read().strip().strip('"')
                        
                        if os.path.exists(img_path):
                            real_img_path = os.path.realpath(img_path)
                            out_name = os.path.splitext(f_name)[0] + ".pfm"
                            out_path = os.path.join(output_dir, out_name)
                            
                            # --- RESUME / CONVERT LOGIC ---
                            # If PFM exists in output but no local cache exists, convert instead of re-running AI
                            existing_pfm = out_path if os.path.exists(out_path) else None
                            cache_name = f"{os.path.basename(real_img_path)}.{self.resolution}.f16.depth"
                            cache_path = os.path.join(os.path.dirname(real_img_path), cache_name)
                            
                            if existing_pfm and self.cache_local and not os.path.exists(cache_path):
                                print(f"[*] RESUME: Converting existing PFM to F16 Cache for {f_name}")
                                pfm_data = load_pfm(existing_pfm)
                                if pfm_data is not None:
                                    pfm_data.astype(np.float16).tofile(cache_path)
                                    print(f"    - Mirrored to: {cache_path}")
                                    processed_mtimes[f_name] = mtime
                                    continue # Skip GPU inference
                            
                            start_t = time.time()
                            self.process_image(img_path, out_path, silent=False)
                            end_t = time.time()
                            duration = end_t - start_t
                            
                            print(f"[+] Completed: {f_name} ({duration:.2f}s)")
                            
                        processed_mtimes[f_name] = mtime
                    except Exception as e:
                        print(f"[!] Error processing {f_name}: {e}")
                
                # Cleanup processed_mtimes cache
                if len(processed_mtimes) > 500:
                    processed_mtimes = {k: v for k, v in processed_mtimes.items() if k in txt_files}

                # Check for Hotkeys (Model Reselect)
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                    if key == 'r':
                        print("\n[!] 'R' pressed. Returning to Model Selection...")
                        if self.device == "cuda": torch.cuda.empty_cache()
                        sys.exit(55) # Special code for restart in launcher
                    elif key == 'q':
                        print("\n[*] Quitting cleanly...")
                        if self.device == "cuda": torch.cuda.empty_cache()
                        sys.exit(0)

                time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n[!] User Interrupted (Ctrl+C). Cleaning up VRAM...")
                if torch.cuda.is_available(): torch.cuda.empty_cache()
                sys.exit(0)
            except Exception as e:
                print(f"[!] Watch error: {e}")
                time.sleep(1)

def load_emu_config():
    config_path = os.path.join(BASE_PATH, "emu_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                # Migration: set defaults for new fields if missing
                if "boost" not in data: data["boost"] = 1.0
                if "cache" not in data: data["cache"] = False
                if "invert" not in data: data["invert"] = True
                if "vanilla_compat" not in data: data["vanilla_compat"] = False
                return data
        except: return None
    return None

def save_emu_config(model, res, bench, boost, cache, invert, vanilla_compat):
    config_path = os.path.join(BASE_PATH, "emu_config.json")
    try:
        with open(config_path, 'w') as f:
            json.dump({
                "model": model, 
                "res": res, 
                "bench": bench,
                "boost": boost,
                "cache": cache,
                "invert": invert,
                "vanilla_compat": vanilla_compat
            }, f)
    except: pass

def show_menu():
    last_cfg = load_emu_config()
    
    print("\n   [ Depth Anything - Configuration ]")
    print("   ----------------------------------")
    
    if last_cfg:
        print(f"   [0] Resume Last: {last_cfg['model']} @ {last_cfg['res']}px (Boost: {last_cfg['boost']}, Cache: {'Y' if last_cfg['cache'] else 'N'}, Standard Flip: {'Y' if last_cfg.get('invert', True) else 'N'}, Vanilla Compat: {'Y' if last_cfg.get('vanilla_compat', False) else 'N'})")
    
    print("   -- Depth Anything V3 (Newest) --")
    print("   [1] DA3-Giant  (4.5GB-8.5GB VRAM)")
    print("   [2] DA3-Large  (2.0GB-4.0GB VRAM)")
    print("   [3] DA3-Metric (2.0GB-4.0GB VRAM)")
    print("   [4] DA3-Base   (1.2GB-1.8GB VRAM)")
    print("   [5] DA3-Small  (0.8GB-1.2GB VRAM)")
    print("   -- Depth Anything V2 (Classic) --")
    print("   [6] DA2-Giant  (Classic High)")
    print("   [7] DA2-Large  (Classic Balanced)")
    print("   [8] DA2-Base   (Classic Fast)")
    print("   [9] DA2-Small  (Classic Mobile)")
    print("   ----------------------------------")
    
    m_choice = input("   Select [0-9]: ").strip()
    
    if m_choice == "0" and last_cfg:
        return (last_cfg['model'], last_cfg['res'], last_cfg['bench'], 
                last_cfg['boost'], last_cfg['cache'], last_cfg.get('invert', True), 
                last_cfg.get('vanilla_compat', False))
        
    m_mapping = {
        "1": "da3-giant", "2": "da3-large", "3": "da3metric-large",
        "4": "da3-base", "5": "da3-small",
        "6": "da2-giant", "7": "v2-large", "8": "v2-base", "9": "v2-small"
    }
    model = m_mapping.get(m_choice, "da3-giant")

    print("\n   [ Inference Resolution ]")
    print("   ------------------------")
    print("   [1] 512  (~1.5GB Extra VRAM)")
    print("   [2] 768  (~3.0GB Extra VRAM)")
    print("   [3] 1024 (~5.0GB Extra VRAM)")
    print("   [4] 1280 (~7.5GB Extra VRAM)")
    print("   [5] 1512 (~9.5GB Extra VRAM)")
    print("   ------------------------")
    
    r_choice = input("   Select [1-5]: ").strip()
    r_mapping = {"1": 512, "2": 768, "3": 1024, "4": 1280, "5": 1512}
    res = r_mapping.get(r_choice, 1024)
    
    print("\n   [ Depth Contrast (Boost) ]")
    print("   --------------------------")
    print("   [1] Standard (Factual)")
    print("   [2] Enhanced (High Contrast)")
    b_choice = input("   Select [1-2]: ").strip()
    boost = 1.25 if b_choice == "2" else 1.0
    
    print("\n   [ Persistence ]")
    print("   ---------------")
    cache = input("   Cache Depth Locally? [y/N]: ").strip().lower() == 'y'
    
    print("\n   [ Inversion ]")
    print("   -------------")
    i_input = input("   Invert Depth (Near=0)? [Y/n]: ").strip().lower()
    invert = False if i_input == 'n' else True

    print("\n   [ Compatibility ]")
    print("   -----------------")
    val_choice = input("   Enable Vanilla Mode (Fixes Flatness/No-Mod)? [y/N]: ").strip().lower()
    vanilla_compat = True if val_choice == 'y' else False
    
    do_bench = input("\n   Run Benchmark? [y/N]: ").strip().lower() == 'y'
    
    save_emu_config(model, res, do_bench, boost, cache, invert, vanilla_compat)
    return model, res, do_bench, boost, cache, invert, vanilla_compat

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Midas DA3 Service")
    parser.add_argument("--model_type", "--model_name", type=str, help="Target model (e.g. da3-giant)")
    parser.add_argument("--input_path", type=str, default="input", help="Input directory")
    parser.add_argument("--output_path", type=str, default="output", help="Output directory")
    parser.add_argument("--continuous", action="store_true", help="Enable watch mode")
    parser.add_argument("--height", type=int, help="Resolution (Inference Size)")
    parser.add_argument("--cache", action="store_true", help="Save depth next to original images")
    parser.add_argument("--delete", action="store_true", help="Ignored")
    parser.add_argument("--optimize", action="store_true", help="Ignored")
    parser.add_argument("--boost", type=float, default=1.0, help="Depth Contrast (Gamma). Try 1.2 or 1.5 for more 'pop'")
    
    parser.add_argument("--benchmark", action="store_true", help="Run 3-pass hardware performance test")
    parser.add_argument("--invert", action="store_true", help="Invert depth (Flip Near/Far)")
    parser.add_argument("--no-invert", action="store_true", help="Force no inversion")
    
    args = parser.parse_args()

    # Ensure directories exist
    os.makedirs(args.input_path, exist_ok=True)
    os.makedirs(args.output_path, exist_ok=True)

    # TUI Model/Res Selection if not forced by CLI
    target_model = args.model_type
    target_res = args.height
    target_bench = args.benchmark
    target_vanilla = False # default

    if not target_model:
        t_model, t_res, t_bench, t_boost, t_cache, t_invert, t_vanilla = show_menu()
        target_model = t_model
        target_res = t_res
        target_bench = t_bench
        target_boost = t_boost
        target_cache = t_cache
        target_invert = t_invert
        target_vanilla = t_vanilla
        print(f"[*] Config: {target_model} @ {target_res}px")
        time.sleep(0.5)
    else:
        last_cfg = load_emu_config()
        target_boost = args.boost
        target_cache = args.cache
        target_invert = True
        
        if last_cfg:
            target_boost = last_cfg.get("boost", target_boost)
            target_cache = last_cfg.get("cache", target_cache)
            target_invert = last_cfg.get("invert", target_invert)
            target_vanilla = last_cfg.get("vanilla_compat", target_vanilla)

    # CLI flag overrides
    if args.invert: target_invert = True
    if args.no_invert: target_invert = False
    if args.cache: target_cache = True

    # Technical Mapping for Game Requests
    technical_mapping = {
        "depth_pro": "da3-giant",
        "DA3o_large": "da3mono-large",
        "DADo_large": "v2-large",  # Factual mapping for DA2
        "DADo_base":  "v2-base",
        "DADo_small": "v2-small",
        "DAD_large":  "da3-giant"
    }
    if target_model in technical_mapping:
        print(f"[*] Technical request '{target_model}' -> Using {technical_mapping[target_model]}")
        target_model = technical_mapping[target_model]

    emulator = MidasEmulator(model_name=target_model, resolution=target_res, boost=target_boost, run_bench=target_bench)
    emulator.cache_local = target_cache
    emulator.invert = target_invert
    emulator.vanilla_compat = target_vanilla
    
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
