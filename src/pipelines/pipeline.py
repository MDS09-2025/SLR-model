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
                     target_sr=48000, noise_reduction=True, chunk_sec=10.0):
    ensure_empty_dir(output_dir)
    exts = (".wav", ".mp3", ".flac", ".ogg", ".m4a")
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(exts)]

    for fname in files:
        path = os.path.join(input_dir, fname)
        print(f"Preprocessing: {path}")
        try:
            y, sr = librosa.load(path, sr=None, mono=True)
            y = librosa.util.normalize(y)
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
            chunk_sec=args.chunk_sec
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
                scale_down(pose, 512)
                p = PoseVisualizer(pose, thickness=2)
                img = p.save_png(None, p.draw(transparency=True))

                # save PNG file
                out_png = os.path.join(args.pose_dir, f"pose_{i:03d}.png")
                with open(out_png, "wb") as f:
                    f.write(img)
                print(f"✅ Saved pose image: {out_png} ({' '.join(words)})")
            else:
                print(f"⚠️ No pose found for line {i}: {gloss_line}")

if __name__ == "__main__":
    main()
