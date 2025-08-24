#!/usr/bin/env python3
"""
Audio → Text → Gloss pipeline

Steps
1) (optional) Preprocess audio: download (YouTube), denoise, resample, chunk
2) Transcribe each audio file with Faster-Whisper
3) Translate transcribed text to gloss with your TransformerModel

"""

import os, sys, json, argparse, re, math
import numpy as np
import soundfile as sf
from collections import defaultdict

# ---------- optional deps (only if you use those steps) ----------
# pip install yt-dlp librosa noisereduce faster-whisper torch
import librosa
import noisereduce
import yt_dlp

import torch
import sys, os

# Add .../SLR-model/src to Python path
SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, SRC_PATH)

from training.t2g_model import TransformerModel
from faster_whisper import WhisperModel

def ensure_empty_dir(path: str):
    os.makedirs(path, exist_ok=True)
    for f in os.listdir(path):
        try:
            os.remove(os.path.join(path, f))
        except IsADirectoryError:
            # if any subfolders ever appear, clear them too
            import shutil
            shutil.rmtree(os.path.join(path, f), ignore_errors=True)

# ---------------------------
# Utility: device selection
# ---------------------------
def pick_device(force_cpu=False):
    if force_cpu:
        return torch.device("cpu")
    # on mac, MPS is fast but some ops may fallback—ASR is fine, T2G safer on CPU
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ---------------------------
# 0) YouTube download (optional)
# ---------------------------
def download_youtube_audio(url_file, output_dir="Raw_Audio", audio_format="mp3"):
    before = set(os.listdir(output_dir)) if os.path.isdir(output_dir) else set()
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
    # start clean so we don't double-transcribe leftovers
    ensure_empty_dir(output_dir)

    exts = (".wav", ".mp3", ".flac", ".ogg", ".m4a")
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(exts)]
    for fname in files:
        path = os.path.join(input_dir, fname)
        print(f"Preprocessing: {path}")
        try:
            # Load the audio file
            y, sr = librosa.load(path, sr=None, mono=True)

            # Normalize the audio 
            y = librosa.util.normalize(y)

            # Resample the audio to the target sample rate
            if sr != target_sr:
                y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
            
            # Apply noise reduction 
            y_proc = noisereduce.reduce_noise(y=y, sr=target_sr) if noise_reduction else y

            # Chunk the audio into smaller segments
            spc = int(chunk_sec * target_sr)
            n_chunks = max(1, int(math.ceil(len(y_proc) / spc)))

            base, _ = os.path.splitext(fname)
            width = len(str(n_chunks))  # zero-pad width

            for i in range(n_chunks):
                start = i * spc
                end = min((i + 1) * spc, len(y_proc))
                chunk = y_proc[start:end]

                # Save the chunked audio file
                out_name = f"{base}_chunk{str(i+1).zfill(width)}.flac"
                out_path = os.path.join(output_dir, out_name)
                sf.write(out_path, chunk, target_sr)
        except Exception as e:
            print(f"  !! error: {e}")
    print("Preprocessing done.")

# ---------------------------
# 2) ASR transcription (Faster-Whisper)
# ---------------------------


def transcribe_dir_grouped(audio_dir, out_dir, model_size="medium",
                           asr_device="cpu", compute_type="float32", beam_size=5, merged_out=None):
    os.makedirs(out_dir, exist_ok=True)

    model = WhisperModel(model_size, device=str(asr_device), compute_type=compute_type)
    exts = (".flac",)
    files = [f for f in os.listdir(audio_dir) if f.lower().endswith(exts)]

    # Group by base name before "_chunk"
    groups = defaultdict(list)
    for fname in files:
        base = re.sub(r"_chunk\d+\.flac$", "", fname)
        groups[base].append(fname)

    for base, chunk_files in groups.items():
        # Sort chunks by number
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
        # Save per-file transcript
        out_path = os.path.join(out_dir, f"{base}.txt")
        with open(out_path, "w") as f:
            f.write("\n".join(all_text))
        print(f"Saved transcript to {out_path}")
     # ----------------------------
    # Merge all transcripts into one
    # ----------------------------
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
# 3) Text → Gloss
# ---------------------------
_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?(?:-[a-z0-9]+)?", re.I)

def tokenize_text(sentence, word_to_index, max_len=64):
    toks = [t.lower() for t in _WORD_RE.findall(sentence)]
    ids = [word_to_index.get(t, word_to_index["<unk>"]) for t in toks]
    ids = ids[:max_len] + [word_to_index["<pad>"]] * (max_len - len(ids))
    return torch.tensor(ids, dtype=torch.long)

def load_t2g(model_path, cfg_path, vocab_path, device):
    with open(cfg_path) as f:
        cfg = json.load(f)
    with open(vocab_path) as f:
        v = json.load(f)

    tw2i = v["text_word_to_index"]
    gw2i = v["gloss_word_to_index"]
    gi2w = {int(i): w for w, i in gw2i.items()}
    pad_text = tw2i["<pad>"]
    pad_gloss = gw2i["<pad>"]

    model = TransformerModel(
        text_vocab_size=len(v["text_vocab"]),
        gloss_vocab_size=len(v["gloss_vocab"]),
        embedding_dim=cfg["embedding_dim"],
        nhead=cfg["nhead"],
        num_encoder_layers=cfg["num_encoder_layers"],
        num_decoder_layers=cfg["num_decoder_layers"],
        dropout=cfg["dropout"],
        max_len=cfg["max_len"],
        pad_index_text=pad_text,
        pad_index_gloss=pad_gloss
    ).to(device)

    state = torch.load(model_path, map_location=device)
    if isinstance(state, dict) and "model_state_dict" in state:
        state = state["model_state_dict"]
    model.load_state_dict(state)
    model.eval()
    return model, tw2i, gw2i, gi2w, cfg

@torch.no_grad()
def decode_beam(model, src_ids, device, tw2i, gw2i, gi2w, max_len=100, beam_size=5, len_penalty=0.6):
    src = src_ids.to(device)
    src_pad_mask = (src.unsqueeze(0) == tw2i["<pad>"]).to(device)
    src_emb = model.positional_encoding(model.text_embedding(src.unsqueeze(0)))
    memory = model.transformer.encoder(src_emb, src_key_padding_mask=src_pad_mask)

    BeamItem = tuple  # (tokens, logprob)
    beams = [(torch.tensor([gw2i["<start>"]], device=device, dtype=torch.long), 0.0)]
    finished = []

    for _ in range(max_len):
        new_beams = []
        for tokens, lp in beams:
            ys = tokens.unsqueeze(0)
            tgt_mask = TransformerModel.generate_square_subsequent_mask(ys.size(1), device=device)
            tgt_pad = torch.zeros(1, ys.size(1), dtype=torch.bool, device=device)
            tgt_emb = model.positional_encoding(model.gloss_embedding(ys))
            out = model.transformer.decoder(
                tgt_emb, memory,
                tgt_mask=tgt_mask,
                tgt_key_padding_mask=tgt_pad,
                memory_key_padding_mask=src_pad_mask
            )
            logits = model.fc_out(out[:, -1])  # [1, V]
            logprobs = torch.log_softmax(logits, dim=-1).squeeze(0)

            topv, topi = torch.topk(logprobs, beam_size)
            for v, idx in zip(topv.tolist(), topi.tolist()):
                next_tokens = torch.cat([tokens, torch.tensor([idx], device=device)])
                next_lp = lp + v
                if idx == gw2i["<end>"]:
                    length = max(1, next_tokens.numel() - 1)
                    score = next_lp / (length ** len_penalty)
                    finished.append((next_tokens.clone(), score))
                else:
                    new_beams.append((next_tokens, next_lp))

        if not new_beams:  # all finished early
            break
        # keep top beam_size by normalized score proxy
        new_beams.sort(key=lambda x: x[1] / (max(1, x[0].numel() - 1) ** len_penalty), reverse=True)
        beams = new_beams[:beam_size]

    if not finished:
        # fall back to best partial
        finished = [(beams[0][0], beams[0][1])]

    finished.sort(key=lambda x: x[1], reverse=True)
    best, _ = finished[0]
    tokens = []
    for idx in best[1:]:  # skip <start>
        w = gi2w[int(idx)]
        if w == "<end>":
            break
        tokens.append(w)
    return " ".join(tokens)

def translate_file(t2g_model, device, tw2i, gw2i, gi2w, in_txt, out_txt,
                   max_src_len=64, max_len=100, decoder="beam", beam_size=5, len_penalty=0.6):
    with open(in_txt, "r") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    results = []
    for ln in lines:
        src = tokenize_text(ln, tw2i, max_len=max_src_len)
        if decoder == "beam":
            gloss = decode_beam(t2g_model, src, device, tw2i, gw2i, gi2w, max_len=max_len,
                                beam_size=beam_size, len_penalty=len_penalty)
        else:
            gloss = decode_greedy(t2g_model, src, device, tw2i, gw2i, gi2w, max_len=max_len)
        results.append(f"{ln}  -->  {gloss}")
        print(results[-1])
    with open(out_txt, "w") as f:
        f.write("\n".join(results))
    print(f"Gloss saved to {os.path.abspath(out_txt)}")

# ---------------------------
# CLI
# ---------------------------
def main():
    ap = argparse.ArgumentParser(description="Audio→Text→Gloss pipeline")
    # steps toggles
    ap.add_argument("--download_youtube", action="store_true", help="Download audio listed in --youtube_urls to Raw_Audio")
    ap.add_argument("--youtube_urls", default="Youtube_urls.txt", help="File with YouTube URLs (one per line)")
    ap.add_argument("--preprocess", action="store_true", help="Run audio preprocessing")
    ap.add_argument("--transcribe", action="store_true", help="Run ASR transcription")
    ap.add_argument("--translate", action="store_true", help="Run text→gloss")

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
    ap.add_argument("--t2g_model", default="transformer_model.pt")
    ap.add_argument("--t2g_config", default="transformer_model_config.json")
    ap.add_argument("--t2g_vocab",  default="transformer_vocab.json")
    ap.add_argument("--t2g_cpu", action="store_true")
    ap.add_argument("--max_src_len", type=int, default=64)
    ap.add_argument("--max_len", type=int, default=100)

    ap.add_argument("--t2g_decoder", choices=["greedy", "beam"], default="beam")
    ap.add_argument("--t2g_beam", type=int, default=8)
    ap.add_argument("--t2g_lenpen", type=float, default=0.7)


    args = ap.parse_args()

    # Step 0: download (optional)
    if args.download_youtube:
        download_youtube_audio(args.youtube_urls, output_dir=args.raw_dir)

    # Step 1: preprocess (optional)
    if args.preprocess:
        preprocess_audio(
            input_dir=args.raw_dir,
            output_dir=args.clean_dir,
            target_sr=args.target_sr,
            noise_reduction=(not args.no_noise_reduction),
            chunk_sec=args.chunk_sec
        )

    # Step 2: transcribe (optional)
    if args.transcribe:
            transcribe_dir_grouped(
            audio_dir=args.clean_dir,
            out_dir="Transcripts",
            model_size=args.whisper_size,
            asr_device=args.asr_device,
            compute_type=args.compute_type,
            beam_size=args.beam_size
    )

    # Step 3: translate (optional)
    if args.translate:
        device = pick_device(force_cpu=args.t2g_cpu)
        model, tw2i, gw2i, gi2w, _ = load_t2g(args.t2g_model, args.t2g_config, args.t2g_vocab, device)
        translate_file(
            model, device, tw2i, gw2i, gi2w,
            in_txt=args.transcript_txt,
            out_txt=args.gloss_txt,
            max_src_len=args.max_src_len,
            max_len=args.max_len,
            # pass the new decoder flags
            decoder=args.t2g_decoder,
            beam_size=args.t2g_beam,
            len_penalty=args.t2g_lenpen,
            merged_out=args.transcript_txt 
        )

if __name__ == "__main__":
    main()




