#!/usr/bin/env python3
"""
Audio → Text → Gloss pipeline

Steps
1) (optional) Preprocess audio: download (YouTube), denoise, resample, chunk
2) Transcribe each audio file with Faster-Whisper
3) Translate transcribed text to gloss with T5-finetuned-ASLG
"""

import os, sys, json, argparse, re, math
import numpy as np
import soundfile as sf
from collections import defaultdict
import multiprocessing as mp
from multiprocessing import Queue, Process

# ---------- optional deps ----------
# pip install yt-dlp librosa noisereduce faster-whisper torch transformers
import librosa
import noisereduce
import yt_dlp
import torch

from transformers import T5Tokenizer, T5ForConditionalGeneration, AutoTokenizer, AutoModelForSeq2SeqLM
from faster_whisper import WhisperModel
from gloss2pose import PoseLookup, scale_down, prepare_glosses
from pose_format.pose_visualizer import PoseVisualizer
import base64, cv2, subprocess

# ---------------------------
# Utility: ensure dir clean
# ---------------------------
def ensure_empty_dir(path: str):
    os.makedirs(path, exist_ok=True)
    for f in os.listdir(path):
        try:
            os.remove(os.path.join(path, f))
        except IsADirectoryError:
            import shutil
            shutil.rmtree(os.path.join(path, f), ignore_errors=True)

# ---------------------------
# Utility: device selection
# ---------------------------
def pick_device(force_cpu=False):
    if force_cpu:
        return torch.device("cpu")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ---------------------------
# Utility: worker cleanup
# ---------------------------
def cleanup_workers(workers):
    """Clean up worker processes with proper termination"""
    print(f"Cleaning up workers...")
    for p in workers:
        p.join(timeout=5)
        if p.is_alive():
            p.terminate()
            p.join(timeout=2)
    print(f"All workers cleaned up.")

# ---------------------------
# Utility: merge transcripts
# ---------------------------
def merge_transcripts(out_dir: str, merged_out: str):
    """Merge all transcript files into a single file"""
    os.makedirs(os.path.dirname(merged_out) or ".", exist_ok=True)
    txts = [f for f in os.listdir(out_dir) if f.lower().endswith(".txt")]
    txts.sort()
    with open(merged_out, "w") as fout:
        for f in txts:
            p = os.path.join(out_dir, f)
            with open(p, "r") as fin:
                text = fin.read().strip()
                if text:
                    fout.write(text + "\n")
    print(f"Merged transcript saved to {os.path.abspath(merged_out)}")

# ---------------------------
# 0) YouTube download (optional)
# ---------------------------
def download_youtube_audio(url_file, output_dir="Raw_Audio", audio_format="mp3"):
    with open(url_file, "r") as f:
        urls = [ln.strip() for ln in f if ln.strip()]
    os.makedirs(output_dir, exist_ok=True)
    ydl_opts = {
        "format": "bestaudio/best",
        "extractaudio": True,
        "audioformat": audio_format,
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": "192",
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(urls)
    print(f"Downloaded {len(urls)} files to {output_dir}")

# ---------------------------
# 1) Parallel Audio Preprocessing
# ---------------------------
def preprocess_single_file(file_info):
    """Process a single audio file"""

    input_path, output_dir, target_sr, noise_reduction, chunk_sec = file_info
    
    fname = os.path.basename(input_path)
    print(f"[Worker {os.getpid()}] Preprocessing: {input_path}")
    
    try:
        # Load and normalize audio
        y, sr = librosa.load(input_path, sr=None, mono=True)
        y = librosa.util.normalize(y)
        
        # Resample if needed
        if sr != target_sr:
            y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
        
        # Apply noise reduction
        y_proc = noisereduce.reduce_noise(y=y, sr=target_sr) if noise_reduction else y

        # Chunk the audio
        spc = int(chunk_sec * target_sr)
        n_chunks = max(1, int(math.ceil(len(y_proc) / spc)))
        base, _ = os.path.splitext(fname)
        width = len(str(n_chunks))

        chunk_files = []
        for i in range(n_chunks):
            start = i * spc
            end = min((i + 1) * spc, len(y_proc))
            chunk = y_proc[start:end]
            out_name = f"{base}_chunk{str(i+1).zfill(width)}.flac"
            out_path = os.path.join(output_dir, out_name)
            sf.write(out_path, chunk, target_sr)
            chunk_files.append(out_name)
        
        return {"success": True, "file": fname, "chunks": chunk_files}
        
    except Exception as e:
        return {"success": False, "file": fname, "error": str(e)}

def preprocess_audio_parallel(input_dir="Raw_Audio", output_dir="Clean_Audio",
                            target_sr=48000, noise_reduction=True, chunk_sec=10.0,
                            num_workers=4):
    """Parallel audio preprocessing"""
    ensure_empty_dir(output_dir)
    exts = (".wav", ".mp3", ".flac", ".ogg", ".m4a")
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(exts)]
    
    if not files:
        print("No audio files found in input directory")
        return
    
    # Prepare work items
    work_items = []
    for fname in files:
        input_path = os.path.join(input_dir, fname)
        work_items.append((input_path, output_dir, target_sr, noise_reduction, chunk_sec))
    
    print(f"Processing {len(files)} files with {num_workers} workers...")
    
    # Process files in parallel
    with mp.Pool(num_workers) as pool:
        pool.map(preprocess_single_file, work_items)

    print("Parallel preprocessing done.")

# ---------------------------
# 2) Parallel ASR Transcription
# ---------------------------
class ASRWorker:
    """Worker process for ASR transcription"""
    
    def __init__(self, worker_id, model_size, asr_device, compute_type, beam_size):
        self.worker_id = worker_id
        self.model_size = model_size
        self.asr_device = asr_device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.model = WhisperModel(model_size, device=str(asr_device), compute_type=compute_type)
    
    def transcribe_file(self, audio_path):
        """Transcribe a single audio file"""

        try:
            print(f"[Worker {self.worker_id}] Transcribing: {audio_path}")
            segments, _ = self.model.transcribe(audio_path, beam_size=self.beam_size)
            
            text_segments = []
            for seg in segments:
                text = seg.text.strip()
                if text:
                    text_segments.append(text)
            
            return {
                "success": True,
                "file": os.path.basename(audio_path),
                "text": text_segments,
                "worker_id": self.worker_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "file": os.path.basename(audio_path),
                "error": str(e),
                "worker_id": self.worker_id
            }

def asr_worker_process(worker_id, model_size, asr_device, compute_type, beam_size, 
                      work_queue, result_queue):
    """Worker process function for ASR"""

    try:
        # Initialize ASR worker
        worker = ASRWorker(worker_id, model_size, asr_device, compute_type, beam_size)
    except Exception as e:
        # Send error back and exit
        result_queue.put({
            "success": False,
            "file": "model_init_failed",
            "error": f"Model initialization failed: {str(e)}",
            "worker_id": worker_id
        })
        return

    while True:
        try:
            # Get work item with timeout = 10s
            item = work_queue.get(timeout=10)
            
            # Check for shutdown sentinel
            if item is None:
                print(f"[Worker {worker_id}] Shutting down")
                break
            
            # Process the audio file
            result = worker.transcribe_file(item)
            result_queue.put(result)
            
        except mp.TimeoutError:
            # No more work items, worker can exit
            print(f"[Worker {worker_id}] done")
            break

        except Exception as e:
            print(f"[Worker {worker_id}] wrong processing: {e}")
            if 'item' in locals():
                result_queue.put({
                    "success": False,
                    "file": os.path.basename(item) if item else "unknown",
                    "error": str(e),
                    "worker_id": worker_id
                })
            break

def transcribe_dir_parallel(audio_dir, out_dir, model_size="medium",
                          asr_device="cpu", compute_type="float32",
                          beam_size=5, merged_out=None, num_workers=2):
    """Parallel ASR transcription with grouped output"""

    os.makedirs(out_dir, exist_ok=True)
    exts = (".flac",)
    files = [f for f in os.listdir(audio_dir) if f.lower().endswith(exts)]
    
    if not files:
        print("No audio files found for transcription")
        return
    
    # Group files by base name (for chunk reassembly)
    groups = defaultdict(list)
    for fname in files:
        base = re.sub(r"_chunk\d+\.flac$", "", fname)
        groups[base].append(fname)
    
    print(f"Found {len(files)} audio files")

    # Memory management based on model size
    if model_size in ["large", "large-v3"] and num_workers > 2:
        print(f"Reducing to 2 workers for stability")
        num_workers = min(2, num_workers)
    elif model_size == "medium" and num_workers > 3:
        print(f"Reducing to 3 workers for stability")
        num_workers = min(3, num_workers)
    
    print(f"Starting parallel transcription with {num_workers} workers...")
    
    # Create queues
    work_queue = Queue()
    result_queue = Queue()
    
    # Add all files to work queue
    for fname in files:
        work_queue.put(os.path.join(audio_dir, fname))
    
    # Add sentinel values for workers
    for _ in range(num_workers):
        work_queue.put(None)
    
    # Start worker processes
    workers = []
    for i in range(num_workers):
        p = Process(
            target=asr_worker_process,
            args=(i, model_size, asr_device, compute_type, beam_size, 
                  work_queue, result_queue)
        )
        p.start()
        workers.append(p)
    
    # Collect results
    results = {}
    completed = 0
    
    while completed < len(files):
        try:
            result = result_queue.get(timeout=60)
            
            completed += 1
            
            if result["success"]:
                results[result["file"]] = result["text"]
                print(f"[{completed}/{len(files)}] Completed: {result['file']} (Worker {result['worker_id']})")
            else:
                print(f"[{completed}/{len(files)}] Failed: {result['file']} - {result['error']} (Worker {result['worker_id']})")
                
        except Exception as e:
            print(f"Error collecting results: {str(e)}")
            print(f"Completed {completed}/{len(files)} files so far")
            # Check if any workers are still alive
            alive_workers = sum(1 for p in workers if p.is_alive())
            print(f"Workers still alive: {alive_workers}")
            if alive_workers == 0:
                print("All workers have been shut down")
                break

    # Clean up workers
    cleanup_workers(workers)
    
    print(f"Transcription completed: {len(results)}/{len(files)} files successful")
    
    # Reassemble grouped transcripts
    print("Reassembling grouped transcripts...")
    for base, chunk_files in groups.items():
        chunk_files.sort(key=lambda f: int(re.search(r"_chunk(\d+)", f).group(1)))
        all_text = []
        
        for fname in chunk_files:
            if fname in results:
                all_text.extend(results[fname])
        
        # Save grouped transcript
        out_path = os.path.join(out_dir, f"{base}.txt")
        with open(out_path, "w") as f:
            f.write("\n".join(all_text))
        print(f"Saved grouped transcript: {out_path}")
    
    # Create merged output if requested
    if merged_out is not None:
        merge_transcripts(out_dir, merged_out)
    
    print(f"Transcription completed!")

# ---------------------------
# 3) Parallel Text → Gloss with T5
# ---------------------------
class T2GWorker:
    """Worker process for Text-to-Gloss translation"""
    
    def __init__(self, worker_id, model_dir, device, max_src_len, max_len, decoder, beam_size, len_penalty):
        self.worker_id = worker_id
        self.device = device
        self.max_src_len = max_src_len
        self.max_len = max_len
        self.decoder = decoder
        self.beam_size = beam_size
        self.len_penalty = len_penalty
        
        # Load model and tokenizer
        model_dir = os.path.abspath(model_dir)
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_dir,
            local_files_only=True,
            use_fast=True
        )
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            model_dir,
            local_files_only=True
        ).to(device)
        self.model.eval()
    
    @torch.no_grad()
    def translate_text(self, text):
        """Translate a single text line to gloss"""
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True,
                                   padding="max_length", max_length=self.max_src_len).to(self.device)

        if self.decoder == "beam":
            outputs = self.model.generate(
                **inputs,
                max_length=self.max_len,
                num_beams=self.beam_size,
                length_penalty=self.len_penalty
            )
        else:
            outputs = self.model.generate(**inputs, max_length=self.max_len)

        gloss = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(gloss)
        return {
                "success": True,
                "text": text,
                "gloss": gloss,
                "worker_id": self.worker_id
            }
            

def t2g_worker_process(worker_id, model_dir, device, max_src_len, max_len, decoder, beam_size, len_penalty,
                      work_queue, result_queue):
    """Worker process function for T2G translation"""
    
    # Set device
    worker = T2GWorker(worker_id, model_dir, device, max_src_len, max_len, decoder, beam_size, len_penalty)

    while True:
        try:
            # Get work item with timeout
            item = work_queue.get(timeout=10)
            
            # Check for shutdown sentinel
            if item is None:
                print(f"[T2G Worker {worker_id}] Shutting down")
                break
            
            # Process the text line
            result = worker.translate_text(item)
            result_queue.put(result)
            
        except mp.TimeoutError:
            # No more work items, worker can exit
            print(f"[T2G Worker {worker_id}] done")
            break

        except Exception as e:
            print(f"[T2G Worker {worker_id}] wrong processing: {e}")
            if 'item' in locals():
                result_queue.put({
                    "success": False,
                    "text": item if item else "unknown",
                    "error": str(e),
                    "worker_id": worker_id
                })
            break

def translate_file_parallel(model_dir, device, in_txt, out_txt,
                           max_src_len=64, max_len=100,
                           decoder="beam", beam_size=5, len_penalty=0.6,
                           num_workers=2):
    """Parallel text-to-gloss translation"""
    
    # Read input text
    with open(in_txt, "r") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    
    if not lines:
        print("No text lines found for translation")
        return
    
    print(f"Translating {len(lines)} lines to gloss using {num_workers} workers...")
    
    # Memory adjustment
    if num_workers > 2:
        print(f"Reducing to 2 workers for stability")
        num_workers = min(2, num_workers)

    # Create queues
    work_queue = Queue()
    result_queue = Queue()
    
    # Add all text lines to work queue
    for line in lines:
        work_queue.put(line)
    
    # Add sentinel values for workers
    for _ in range(num_workers):
        work_queue.put(None)
    
    # Start worker processes
    workers = []
    for i in range(num_workers):
        p = Process(
            target=t2g_worker_process,
            args=(i, model_dir, device, max_src_len, max_len, decoder, beam_size, len_penalty,
                  work_queue, result_queue)
        )
        p.start()
        workers.append(p)
    
    # Collect results
    results = {}
    completed = 0
    
    while completed < len(lines):
        try:
            result = result_queue.get(timeout=100)
            
            completed += 1
            
            if result["success"]:
                # Store result with original line index to preserve order
                line_index = lines.index(result["text"])
                results[line_index] = result["gloss"]
                print(f"[{completed}/{len(lines)}] Completed: {result['gloss'][:50]}... (Worker {result['worker_id']})")
            else:
                print(f"[{completed}/{len(lines)}] Failed: {result['text'][:50]}... - {result['error']} (Worker {result['worker_id']})")
                
        except Exception as e:
            print(f"Error collecting T2G results: {str(e)}")
            print(f"Completed {completed}/{len(lines)} translations so far")
            # Check if any workers are still alive
            alive_workers = sum(1 for p in workers if p.is_alive())
            print(f"T2G Workers still alive: {alive_workers}")
            if alive_workers == 0:
                print("All T2G workers have been shut down")
                break
    
    # Clean up workers
    cleanup_workers(workers)
    
    print(f"T2G translation completed: {len(results)}/{len(lines)} lines successful")
    
    # Write results in original order
    final_results = []
    for i in range(len(lines)):
        if i in results:
            final_results.append(results[i])
    
    with open(out_txt, "w") as f:
        f.write("\n".join(final_results))
    print(f"Gloss saved to {os.path.abspath(out_txt)}")

def resample_pose_manual(pose, new_fps: int):
    """Resample pose to new fps using numpy interpolation (supports 3D/4D)."""
    import numpy as np

    old_fps = getattr(pose.body, "fps", getattr(pose, "fps", None))
    if not old_fps or old_fps == new_fps:
        return pose

    old_data = pose.body.data
    old_frames = old_data.shape[0]
    duration = old_frames / old_fps
    new_frames = int(round(duration * new_fps))

    # Flatten everything except frames
    flat = old_data.reshape(old_frames, -1)

    old_idx = np.linspace(0, old_frames - 1, num=old_frames)
    new_idx = np.linspace(0, old_frames - 1, num=new_frames)

    # Interpolate each flattened feature
    new_flat = np.vstack([
        np.interp(new_idx, old_idx, flat[:, j])
        for j in range(flat.shape[1])
    ]).T  # shape (new_frames, features)

    # Reshape back to original structure
    new_data = new_flat.reshape(new_frames, *old_data.shape[1:])

    pose.body.data = new_data.astype(old_data.dtype)
    pose.body.fps = new_fps
    return pose

def get_video_fps(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps if fps and fps > 0 else None

def trim_empty_frames(pose):
    """
    Remove frames that contain only zeros (no keypoints).
    Works for (frames, points, coords) or (frames, persons, points, coords).
    """
    data = pose.body.data
    ndim = data.ndim

    if ndim == 3:  # (frames, points, coords)
        mask = (data != 0).any(axis=(1, 2))
    elif ndim == 4:  # (frames, persons, points, coords)
        mask = (data != 0).any(axis=(1, 2, 3))
    else:
        print(f"⚠️ Unexpected pose shape {data.shape}, skipping trim")
        return pose

    if mask.any():
        pose.body.data = data[mask]
    return pose

def trim_leading_static_frames(pose, threshold=5):
    """
    Remove leading frames where pose is static (same as next frame).
    threshold = how many frames must differ before we consider 'motion starts'.
    """
    data = pose.body.data
    diffs = np.abs(np.diff(data, axis=0)).sum(axis=(1, 2))  # motion magnitude per frame
    motion_start = np.argmax(diffs > 1e-6)  # first frame with real motion
    if motion_start > threshold:
        pose.body.data = data[motion_start:]
    return pose

def shift_pose(pose, dx: int = 0, dy: int = 0):
    """Shift pose coordinates by (dx, dy) pixels."""
    pose.body.data[..., 0] += dx  # x-axis shift
    pose.body.data[..., 1] += dy  # y-axis shift
    return pose

def shrink_pose_only(pose, factor: float = 0.5):
    """
    Shrink skeleton coordinates (x,y) but keep pose header dimensions unchanged.
    """
    pose.body.data[..., 0] *= factor  # x coords
    pose.body.data[..., 1] *= factor  # y coords
    return pose

def extend_video_to_match_pose(video_path, out_path, target_frames, fps):
    """Extend video by freezing the last frame until target_frames."""
    cap = cv2.VideoCapture(video_path)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    last_frame = frames[-1]
    while len(frames) < target_frames:
        frames.append(last_frame)

    h, w, _ = frames[0].shape
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    for f in frames:
        out.write(f)
    out.release()
    return out_path


def extend_pose_to_match_video(pose, target_frames):
    """Extend pose frames by repeating the last one until target_frames."""
    data = pose.body.data
    conf = pose.body.confidence
    last_frame = data[-1:]
    last_conf = conf[-1:]

    repeat = target_frames - data.shape[0]
    if repeat > 0:
        data = np.concatenate([data, np.repeat(last_frame, repeat, axis=0)], axis=0)
        conf = np.concatenate([conf, np.repeat(last_conf, repeat, axis=0)], axis=0)

    pose.body.data = data
    pose.body.confidence = conf
    return pose

import subprocess

def merge_audio(audio_source, overlay_video, out_video, pad_to_duration):
    """
    Combine overlay video with external audio file (.wav/.mp3)
    or fallback to original video audio.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", overlay_video,
        "-i", audio_source,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",   # video from overlay
        "-map", "1:a:0"   # audio from source
    ]
    if pad_to_duration:
        cmd += ["-t", str(pad_to_duration)]  # force total duration
    cmd.append(out_video)
    subprocess.run(cmd, check=True)
    print(f"[INFO] Final video with audio → {out_video}")

def pad_audio_to_pose(audio_in, out_audio, target_frames, fps):
    """
    Pad audio with silence so its duration matches the pose video.
    """
    target_duration = target_frames / fps  # seconds
    cmd = [
        "ffmpeg", "-y",
        "-i", audio_in,
        "-af", f"apad=pad_dur={target_duration}",
        "-t", str(target_duration),
        out_audio
    ]
    subprocess.run(cmd, check=True)
    print(f"[INFO] Padded audio → {out_audio} ({target_duration:.2f}s)")
    return out_audio


# ---------------------------
# CLI
# ---------------------------
def main():
    ap = argparse.ArgumentParser(description="Audio→Text→Gloss pipeline")
    # step toggles
    ap.add_argument("--download_youtube", action="store_true")
    ap.add_argument("--youtube_urls", default="Youtube_urls.txt")
    ap.add_argument("--preprocess", action="store_true")
    ap.add_argument("--transcribe", action="store_true")
    ap.add_argument("--translate", action="store_true")

    # dirs/files
    ap.add_argument("--raw_dir", default="Raw_Audio")
    ap.add_argument("--clean_dir", default="Clean_Audio")
    ap.add_argument("--transcript_txt", default="transcription_output.txt")
    ap.add_argument("--gloss_txt", default="gloss_output.txt")

    # preprocess opts
    ap.add_argument("--target_sr", type=int, default=48000)
    ap.add_argument("--chunk_sec", type=float, default=10.0)
    ap.add_argument("--no_noise_reduction", action="store_true")

    # ASR opts
    ap.add_argument("--whisper_size", default="large-v3")
    ap.add_argument("--asr_device", default="cpu", choices=["cpu","cuda","mps"])
    ap.add_argument("--compute_type", default="float32")
    ap.add_argument("--beam_size", type=int, default=5)
    
    # Parallel processing options
    ap.add_argument("--preprocess_workers", type=int, default=4)
    ap.add_argument("--asr_workers", type=int, default=2)
    ap.add_argument("--t2g_workers", type=int, default=2)

    # T2G opts
    ap.add_argument("--t2g_model", default="t5-finetuned-aslg")
    ap.add_argument("--t2g_cpu", action="store_true")
    ap.add_argument("--max_src_len", type=int, default=64)
    ap.add_argument("--max_len", type=int, default=100)
    ap.add_argument("--t2g_decoder", choices=["greedy", "beam"], default="beam")
    ap.add_argument("--t2g_beam", type=int, default=8)
    ap.add_argument("--t2g_lenpen", type=float, default=0.7)
    ap.add_argument("--render_pose", action="store_true")
    ap.add_argument("--pose_dir", default="Pose_Output")
    ap.add_argument("--gloss2pose_dir", default="../../data/gloss2pose")
    ap.add_argument("--job_id", required=False, help="Unique job identifier")
    ap.add_argument("--input_video", type=str, help="Path to original video for overlay", required=False)

    args = ap.parse_args()

    # Step 0
    if args.download_youtube:
        download_youtube_audio(args.youtube_urls, output_dir=args.raw_dir)

    # Step 1
    if args.preprocess:
        preprocess_audio_parallel(
            input_dir=args.raw_dir,
            output_dir=args.clean_dir,
            target_sr=args.target_sr,
            noise_reduction=(not args.no_noise_reduction),
            chunk_sec=args.chunk_sec,
            num_workers=args.preprocess_workers
        )

    # Step 2
    if args.transcribe:
        transcribe_dir_parallel(
            audio_dir=args.clean_dir,
            out_dir="Transcripts",
            model_size=args.whisper_size,
            asr_device=args.asr_device,
            compute_type=args.compute_type,
            beam_size=args.beam_size,
            merged_out=args.transcript_txt,
            num_workers=args.asr_workers
        )

    # Step 3
    if args.translate:
        print("\n--- Step 3: Parallel Text-to-Gloss Translation ---")
        device = pick_device(force_cpu=args.t2g_cpu)
        translate_file_parallel(
                model_dir=args.t2g_model,
                device=device,
                in_txt=args.transcript_txt,
                out_txt=args.gloss_txt,
                max_src_len=args.max_src_len,
                max_len=args.max_len,
                decoder=args.t2g_decoder,
                beam_size=args.t2g_beam,
                len_penalty=args.t2g_lenpen,
                num_workers=args.t2g_workers
            )
        print(">>> Parallel Text-to-Gloss translation completed!")

        # Step 4: Gloss → Pose
    if args.render_pose:
        os.makedirs(args.pose_dir, exist_ok=True)
        lookup = PoseLookup(directory=args.gloss2pose_dir, language="asl")
        with open(args.gloss_txt, "r") as f:
            lines = [ln.strip() for ln in f if ln.strip()]

        for i, gloss_line in enumerate(lines, start=1):
            glosses = prepare_glosses(gloss_line)
            pose, words = lookup.gloss_to_pose(glosses)

            if pose:
                pose = trim_empty_frames(pose)
                pose = trim_leading_static_frames(pose)
                if pose.body.data.shape[0] == 0:
                    print(f"⚠️ Empty pose skipped for line {i}")
                    continue
                scale_down(pose, 512)
                p = PoseVisualizer(pose, thickness=2)

                if hasattr(args, "input_video") and args.input_video and os.path.exists(args.input_video):
                    # shrink skeleton only (video unaffected)
                    pose = shrink_pose_only(pose, factor=0.5)
                    pose = shift_pose(pose, dx=300, dy=300)

                    video_fps = get_video_fps(args.input_video)
                    pose_fps = getattr(pose.body, "fps", video_fps or 25)
                    if video_fps:
                        video_cap = cv2.VideoCapture(args.input_video)
                        video_frames = int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        video_cap.release()
                        pose = resample_pose_manual(pose, int(round(video_fps)))

                        pose_frames = pose.body.data.shape[0]
                        if pose_frames > video_frames:
                            extended_video = os.path.join(args.pose_dir, f"{args.job_id}_extended.mp4")
                            extend_video_to_match_pose(args.input_video, extended_video, pose_frames, int(video_fps))
                            input_video_for_overlay = extended_video
                        else:
                            # extend pose
                            pose = extend_pose_to_match_video(pose, video_frames)
                            input_video_for_overlay = args.input_video
                        
                        
                        p = PoseVisualizer(pose, thickness=2)

                        out_path = os.path.join(args.pose_dir, f"{args.job_id}_overlay.mp4")
                        p.save_video(out_path, p.draw_on_video(input_video_for_overlay))
                        print(f"[INFO] Overlay video saved → {out_path}")

                        # Merge back audio from original video
                        final_path = out_path.replace("_overlay", "_final")
                        video_base = os.path.splitext(os.path.basename(args.input_video))[0]
                        possible_exts = [".wav", ".mp3", ".flac", ".m4a"]

                        audio_source = None

                        for ext in possible_exts:
                            candidate = os.path.join(args.raw_dir, f"{video_base}{ext}")
                            if os.path.exists(candidate):
                                audio_source = candidate
                                break

                        # 2. Fallback: use input video’s audio
                        if audio_source is None:
                            print("⚠️ No matching raw audio found, falling back to input video audio")
                            audio_source = args.input_video
                        job_root = os.path.abspath(os.path.join(args.pose_dir, ".."))  # one level up from Pose_Output

                        # Merge into final video
                        final_path = os.path.join(job_root, f"{args.job_id}.mp4")
                        merge_audio(audio_source, out_path, final_path, pad_to_duration=pose_frames/pose_fps)
                        
                else:
                    pose_frames = pose.body.data.shape[0]
                    pose_fps = getattr(pose.body, "fps", 25)
                    p.save_video(f"{args.job_id}.mp4", p.draw())
                    base_audio = None
                    for f in os.listdir(args.raw_dir):
                        if f.lower().endswith((".wav", ".mp3", ".flac", ".m4a")):
                            base_audio = os.path.join(args.raw_dir, f)
                            print(f"[INFO] Using fallback audio: {base_audio}")
                            break
                    if os.path.exists(base_audio):
                        padded_audio = os.path.join(args.pose_dir, f"{args.job_id}_padded.wav")
                        pad_audio_to_pose(base_audio, padded_audio, pose_frames, pose_fps)
                        # Move padded audio to job root so ASP.NET can serve it
                        job_root = os.path.dirname(os.path.dirname(padded_audio))  # one level up
                        final_audio = os.path.join(job_root, f"{args.job_id}.wav")
                        os.replace(padded_audio, final_audio)
                        print(f"[INFO] Moved padded audio to {final_audio}")
                    else:
                        print("⚠️ No audio file found to pad")


                pose_filename = f"{args.job_id}.pose" if args.job_id else f"pose_{i:03d}.pose"
                out_pose = os.path.join(args.pose_dir, pose_filename)
                with open(out_pose, "wb") as f:
                    pose.write(f) # serialize pose to bytes
                print(f"💾 Saved pose file: {out_pose}")
            else:
                print(f"⚠️ No pose found for line {i}: {gloss_line}")

if __name__ == "__main__":
    # Set multiprocessing start method for cross-platform compatibility
    mp.set_start_method('spawn', force=True)
    main()
