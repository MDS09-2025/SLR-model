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

# ---------- optional deps ----------
# pip install yt-dlp librosa noisereduce faster-whisper torch transformers
import librosa
import noisereduce
import yt_dlp
import torch

from transformers import T5Tokenizer, T5ForConditionalGeneration
from faster_whisper import WhisperModel
from gloss2pose import PoseLookup, scale_down, prepare_glosses
from pose_format.pose_visualizer import PoseVisualizer
import base64, cv2

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
# 1) Audio preprocessing
# ---------------------------
def preprocess_audio(input_dir="Raw_Audio", output_dir="Clean_Audio",
                     target_sr=48000, noise_reduction=True, chunk_sec=10.0, trim_silence = True, top_db = 30):
    ensure_empty_dir(output_dir)
    exts = (".wav", ".mp3", ".flac", ".ogg", ".m4a")
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(exts)]

    for fname in files:
        path = os.path.join(input_dir, fname)
        print(f"Preprocessing: {path}")
        try:
            y, sr = librosa.load(path, sr=None, mono=True)
            y = librosa.util.normalize(y)
            if trim_silence:
                yt, idx = librosa.effects.trim(y, top_db=top_db)
                print(f"  Trimmed {len(y) - len(yt)} samples of silence")
                y = yt
            if sr != target_sr:
                y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
            y_proc = noisereduce.reduce_noise(y=y, sr=target_sr) if noise_reduction else y

            spc = int(chunk_sec * target_sr)
            n_chunks = max(1, int(math.ceil(len(y_proc) / spc)))
            base, _ = os.path.splitext(fname)
            width = len(str(n_chunks))

            for i in range(n_chunks):
                start = i * spc
                end = min((i + 1) * spc, len(y_proc))
                chunk = y_proc[start:end]
                out_name = f"{base}_chunk{str(i+1).zfill(width)}.flac"
                out_path = os.path.join(output_dir, out_name)
                sf.write(out_path, chunk, target_sr)
        except Exception as e:
            print(f"  !! error: {e}")
    print("Preprocessing done.")

# ---------------------------
# 2) ASR transcription
# ---------------------------
def transcribe_dir_grouped(audio_dir, out_dir, model_size="medium",
                           asr_device="cpu", compute_type="float32",
                           beam_size=5, merged_out=None):
    os.makedirs(out_dir, exist_ok=True)
    model = WhisperModel(model_size, device=str(asr_device), compute_type=compute_type)

    exts = (".flac",)
    files = [f for f in os.listdir(audio_dir) if f.lower().endswith(exts)]

    groups = defaultdict(list)
    for fname in files:
        base = re.sub(r"_chunk\d+\.flac$", "", fname)
        groups[base].append(fname)

    for base, chunk_files in groups.items():
        chunk_files.sort(key=lambda f: int(re.search(r"_chunk(\d+)", f).group(1)))
        all_text = []
        for fname in chunk_files:
            fpath = os.path.join(audio_dir, fname)
            print(f"Transcribing: {fpath}")
            segments, _ = model.transcribe(fpath, beam_size=beam_size)
            for seg in segments:
                text = seg.text.strip()
                if text:
                    all_text.append(text)
                    print(text)
        out_path = os.path.join(out_dir, f"{base}.txt")
        with open(out_path, "w") as f:
            f.write("\n".join(all_text))
        print(f"Saved transcript to {out_path}")

    if merged_out is not None:
        with open(merged_out, "w") as fout:
            for base in sorted(groups.keys()):
                per_file = os.path.join(out_dir, f"{base}.txt")
                if os.path.exists(per_file):
                    with open(per_file, "r") as fin:
                        text = fin.read().strip()
                        if text:
                            fout.write(text + "\n")
        print(f"Merged transcript saved to {merged_out}")

# ---------------------------
# 3) Text → Gloss with T5
# ---------------------------
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

def load_t2g(model_dir, device):
    model_dir = os.path.abspath(model_dir)
    print(">>> Resolved model path:", model_dir)

    # Use AutoTokenizer / AutoModel and force local loading
    tokenizer = AutoTokenizer.from_pretrained(
        model_dir,
        local_files_only=True,
        use_fast=True
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_dir,
        local_files_only=True
    ).to(device)

    model.eval()
    return model, tokenizer

@torch.no_grad()
def translate_file(model, tokenizer, device, in_txt, out_txt,
                   max_src_len=64, max_len=100,
                   decoder="beam", beam_size=5, len_penalty=0.6):
    with open(in_txt, "r") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    results = []
    for ln in lines:
        inputs = tokenizer(ln, return_tensors="pt", truncation=True,
                           padding="max_length", max_length=max_src_len).to(device)

        if decoder == "beam":
            outputs = model.generate(
                **inputs,
                max_length=max_len,
                num_beams=beam_size,
                length_penalty=len_penalty
            )
        else:
            outputs = model.generate(**inputs, max_length=max_len)

        gloss = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(gloss)
        results.append(gloss)

    with open(out_txt, "w") as f:
        f.write("\n".join(results))
    print(f"Gloss saved to {os.path.abspath(out_txt)}")

# ---------------------------
# Utility: merge transcripts
# ---------------------------
def merge_transcripts(out_dir: str, merged_out: str):
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
        preprocess_audio(
            input_dir=args.raw_dir,
            output_dir=args.clean_dir,
            target_sr=args.target_sr,
            noise_reduction=(not args.no_noise_reduction),
            chunk_sec=args.chunk_sec,
            trim_silence=True
        )

    # Step 2
    if args.transcribe:
        transcribe_dir_grouped(
            audio_dir=args.clean_dir,
            out_dir="Transcripts",
            model_size=args.whisper_size,
            asr_device=args.asr_device,
            compute_type=args.compute_type,
            beam_size=args.beam_size,
            merged_out=args.transcript_txt
        )

    # Step 3
    if args.translate:
        print(">>> Starting T2G step...")
        device = pick_device(force_cpu=args.t2g_cpu)
        print(">>> Loading model from:", args.t2g_model)
        model, tokenizer = load_t2g(args.t2g_model, device)
        print(">>> Model loaded successfully")
        translate_file(
            model, tokenizer, device,
            in_txt=args.transcript_txt,
            out_txt=args.gloss_txt,
            max_src_len=args.max_src_len,
            max_len=args.max_len,
            decoder=args.t2g_decoder,
            beam_size=args.t2g_beam,
            len_penalty=args.t2g_lenpen
        )
        print(">>> Translation finished. Gloss saved.")

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
    main()
