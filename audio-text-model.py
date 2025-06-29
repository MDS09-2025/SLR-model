"""
This script is to trascribe audio into text using Faster Whisper Model

Author: Shee Xuen Han
Last Modified: 2025-05-08
Version: 1.0.0
"""
# Install dependencies if needed
# !pip install git+https://github.com/SYSTRAN/faster-whisper.git
# !sudo apt update && sudo apt install ffmpeg

from faster_whisper import WhisperModel

model_size = "large-v3"

model = WhisperModel(model_size, device="cuda", compute_type="float16")

segments, info = model.transcribe("Clean_Audio/1585-157660-0000_chunk1.flac", beam_size=5)

full_text = []

for segment in segments:
    line = segment.text
    print(line)
    full_text.append(line)

final_transcription = "\n".join(full_text)

# Save to a text file
with open("transcription_output.txt", "w") as f:
    f.write(final_transcription)


