#!/usr/bin/env python3
"""Download and setup Vosk model for offline speech recognition."""

import os
import sys
import urllib.request
import zipfile
from pathlib import Path

MODEL_URLS = {
    "en-us": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    "en-us-large": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip",
}

def download_model(model_name: str = "en-us", dest_dir: str = None):
    """Download and extract Vosk model."""
    if dest_dir is None:
        dest_dir = Path.home() / ".active_assistant" / "models" / "vosk"
    
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = dest_dir / model_name
    
    if model_path.exists():
        print(f"Model already exists at {model_path}")
        return str(model_path)
    
    url = MODEL_URLS.get(model_name)
    if not url:
        print(f"Unknown model: {model_name}")
        print(f"Available: {list(MODEL_URLS.keys())}")
        return None
    
    zip_path = dest_dir / f"{model_name}.zip"
    
    print(f"Downloading {model_name} model from {url}...")
    
    try:
        def progress_hook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, downloaded * 100 / total_size)
                sys.stdout.write(f"\rProgress: {percent:.1f}%")
                sys.stdout.flush()
        
        urllib.request.urlretrieve(url, zip_path, progress_hook)
        print("\nDownload complete. Extracting...")
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(dest_dir)
        
        # Find extracted folder (may have different name)
        extracted = list(dest_dir.glob("vosk-model*"))
        if extracted:
            extracted[0].rename(model_path)
        
        zip_path.unlink()  # Remove zip
        
        print(f"Model installed at: {model_path}")
        return str(model_path)
        
    except Exception as e:
        print(f"Error downloading model: {e}")
        if zip_path.exists():
            zip_path.unlink()
        return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download Vosk speech recognition model")
    parser.add_argument("--model", default="en-us", choices=list(MODEL_URLS.keys()),
                        help="Model to download")
    parser.add_argument("--dir", help="Destination directory")
    args = parser.parse_args()
    
    path = download_model(args.model, args.dir)
    if path:
        print(f"\nSuccess! Model ready at: {path}")
        print(f"Set VOSK_MODEL_PATH={path} or configure in config.yaml")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()