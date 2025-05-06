"""
This script is purposed to conduct audio preprocessing on datasets such as
YouTube Videos, LibriSpeech, and Common Voice. The preprocessed audio files
will be used for speech to text transcription, and training + enhancing the
Whisper model.

Author: Ashley Yow Shu Ping
Last Modified: 2025-05-06
Version: 1.0.0
"""

import os
import yt_dlp
import librosa
import soundfile as sf
import noisereduce
import numpy as np


def download_youtube_audio(video_url_file='Youtube_urls.txt', output_path='Raw_Audio', audio_format='mp3'):
    """
    Download audio from a YouTube video and save it in the specified format.

    :Input:
    video_url_file (str): The file containing YouTube video URLs (one per line).
    output_path (str): The directory to save the downloaded audio file.
    audio_format (str): The desired audio format.
    """

    # Read the video URLs from the file
    with open(video_url_file, 'r') as file:
        video_urls = [line.strip() for line in file if line.strip()] 

    # Check if the output directory exists, if not, create it
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Set up the options for yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': audio_format,
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': audio_format,
            'preferredquality': '192',
        }],
    }

    # Download the audio from the video URLs
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(video_urls)
    
    print(f"Downloaded {len(video_urls)} audio files to {output_path}.")


def preprocess_audio(input_path='Raw_Audio', output_path='Clean_Audio', target_sr=48000, 
                     noise_reduction=True, chunk_size=10.0):
    """
    This function preprocesses audio files by conducting audio normalization,
    resampling, applying noise reduction, audio chunking, and saving the processed
    audio files.

    :Input:
    input_path (str): The directory containing the raw audio files.
    output_path (str): The directory to save the preprocessed audio files.
    target_sr (int): The target sample rate for resampling.
    noise_reduction (bool): Whether to apply noise reduction.
    chunk_size (float): The size of each audio chunk in seconds.
    """

    # Check if the output directory exists, if not, create it
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Iterate through all files in the input directory
    for filename in os.listdir(input_path):
        if not filename.lower().endswith(('.wav', '.mp3', '.flac', '.ogg', '.m4a')):
            continue  # Skip non-audio files

        file_path = os.path.join(input_path, filename)
        print(f"Processing {file_path}...")

        try:
            # Load the audio file
            y, sr = librosa.load(file_path, sr=None)

            # Normalize the audio
            y = librosa.util.normalize(y)

            # Resample the audio to the target sample rate
            if sr != target_sr:
                y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)

            # Apply noise reduction if specified
            if noise_reduction:
                y_denoised = noisereduce.reduce_noise(y=y, sr=target_sr)

            # Chunk the audio into smaller segments
            samples_per_chunk = int(chunk_size * target_sr)
            num_chunks = int(np.ceil(len(y_denoised) / samples_per_chunk))

            basename, ext = os.path.splitext(filename)
            for i in range(num_chunks):
                start = i * samples_per_chunk
                end = min((i + 1) * samples_per_chunk, len(y_denoised))
                chunk = y_denoised[start:end]

                # Save the chunked audio file
                chunk_filename = f"{basename}_chunk{i+1}{ext}"
                chunk_path = os.path.join(output_path, chunk_filename)
                sf.write(chunk_path, chunk, target_sr)
        
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print("Audio preprocessing completed.")


download_youtube_audio()
preprocess_audio()