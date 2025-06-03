"""
This script is purposed to conduct text preprocessing on text datasets such as
transcribed audio files from YouTube videos, ASLG-PC12 Corpus, and How2Sign. The 
preprocessed text files will be used for text to gloss conversion, and cleaned
datasets will be used for training and testing of the Syntax Aware Transformer 
Model.

Author: Ashley Yow Shu Ping
Last Modified: 2025-06-03
Version: 1.1.0
"""

import os
import re
import spacy

def clean_text(line):
    """
    Clean the input text by removing punctuations and unwanted whitespaces.

    :Input:
        line (str): The input text line to be cleaned.
    :Return:
        line (str): The cleaned text line.
    """
    # Convert to lowercase
    line = line.lower()

    # Remove punctuation
    line = re.sub(r'[^\w\s]', '', line)
    
    # Remove extra whitespace
    line = re.sub(r'\s+', ' ', line).strip()
    
    return line


def preprocess_file(input_file, output_file, nlp):
    """
    Preprocess the text data by cleaning and tokenizing it using spaCy.
    :Input:
        input_file (str): The path to the input text file.
        output_file (str): The path to the output text file where preprocessed 
                           data will be saved.
        nlp (spacy.lang): The spaCy language model for tokenization.
    """
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8') as outfile:
        for line in infile:
            cleaned_line = clean_text(line)
            if cleaned_line:
                # Use spaCy to tokenize the cleaned line
                doc = nlp(cleaned_line)
                tokens = [token.text for token in doc]
                outfile.write(' '.join(tokens) + '\n')


def batch_preprocess(input_dir='Raw_Text', output_dir='Clean_Text'):
    """
    Batch preprocess text files in the input directory and save them to 
    the output directory.
    
    :Input:
        input_dir (str): The directory containing input text files.
        output_dir (str): The directory to save preprocessed text files.
        nlp (spacy.lang): The spaCy language model for tokenization.
    """
    # Check if output directory exists, if not, create it
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Load the spaCy language model
    print("Loading spaCy language model...")
    nlp = spacy.load("en_core_web_sm")

    # List all text files in the input directory
    txt_files = [f for f in os.listdir(input_dir) if f.endswith('.txt')]
    if not txt_files:
        print("No text files found in the input directory.")
        return
    
    print(f"Found {len(txt_files)} text files. Preprocessing...")

    # Iterate through all text files in the input directory
    for txt_file in txt_files:
        input_file = os.path.join(input_dir, txt_file)
        output_file = os.path.join(output_dir, f"cleaned_{txt_file}")
        print(f"Preprocessing {input_file}...")
        preprocess_file(input_file, output_file, nlp)
        print(f"Saved preprocessed text to {output_file}.")


batch_preprocess(input_dir='Raw_Text', output_dir='Clean_Text')

