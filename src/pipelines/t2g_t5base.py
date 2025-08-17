from transformers import T5Tokenizer, T5ForConditionalGeneration
import csv
import torch
import pandas as pd

model_path = "t5-finetuned-aslg"
tokenizer = T5Tokenizer.from_pretrained(model_path)
model = T5ForConditionalGeneration.from_pretrained(model_path)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# sentences = [
#     "i should nt be miserable and i went on a riverrafting trip by myself because i had no social life",
#     "i am talking about the powerful effects of physical activity",
#     "i ve always been fascinated with the hippocampus how could it be that an event that lasts just a moment",
#     "i came back thinking oh my god i was the weakest person on that trip,"
#     "i came back with a mission i said i m never going to feel like the weakest person on a riverrafting trip again"
# ]

# Generate glosses
# for i, sentence in enumerate(sentences):
#     prompted_sentence = "translate English to gloss: " + sentence  # ✅ Add prompt inside loop
#     inputs = tokenizer(prompted_sentence, return_tensors="pt", truncation=True, padding=True).to(device)
#     inputs = tokenizer(sentence, return_tensors="pt", truncation=True, padding=True).to(device)
#     output = model.generate(
#     **inputs,
#     max_length=512,
#     num_beams=4,
#     early_stopping=False
# )
#     gloss = tokenizer.decode(output[0], skip_special_tokens=True)
#     print(f"🗣️ Input {i+1}: {sentence}")
#     print(f"👐 Gloss {i+1}: {gloss}\n")

# ----------------------------- Second Test --------------------------------------------
# Load the clean corpus
with open("Transcripts/Elon Says Goodbye to Trump Administration & Trump’s Response Is Perfect.txt", "r") as f:
    lines = [line.strip() for line in f if line.strip()]

with open("gloss_elon_t5.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Input", "Generated Gloss"])

    for line in lines:
        inputs = tokenizer(line, return_tensors="pt", truncation=True, padding=True).to(model.device)
        output = model.generate(
        **inputs,
        max_length=512,
        num_beams=5,
        length_penalty = 1.3,
        repetition_penalty = 1.2,
        no_repeat_ngram_size=2,
        early_stopping=False
        )
        gloss = tokenizer.decode(output[0], skip_special_tokens=True)
        writer.writerow([line, gloss])

# ----------------------------- Third Test --------------------------------------------
# test_df = pd.read_csv("test_dataset.csv") 
# with open("gloss_mismatches.csv", "w", newline="") as csvfile:
#     writer = csv.writer(csvfile)
#     writer.writerow(["Input", "Target Gloss", "Predicted Gloss"])  # Header

#     for idx, row in test_df.iterrows():
#         input_text = row["input"]
#         target_gloss = row["target"]

#         # Generate prediction
#         inputs = tokenizer(input_text, return_tensors="pt", truncation=True, padding=True).to(device)
#         output = model.generate(
#             **inputs,
#             max_length=512,
#             num_beams=4,
#             early_stopping=False
#         )
#         predicted_gloss = tokenizer.decode(output[0], skip_special_tokens=True)

#         # Log mismatches
#         if predicted_gloss.strip().upper() != target_gloss.strip().upper():
#             writer.writerow([input_text, target_gloss, predicted_gloss])
