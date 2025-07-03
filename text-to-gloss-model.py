from transformers import T5Tokenizer, T5ForConditionalGeneration
import csv

model_path = "/Users/xuenhan/Downloads/t5-finetuned-aslg"
tokenizer = T5Tokenizer.from_pretrained(model_path)
model = T5ForConditionalGeneration.from_pretrained(model_path)

# Load the clean corpus
with open("Clean_Text/cleaned_corpus_0009.clean.en.txt", "r") as f:
    lines = [line.strip() for line in f if line.strip()]

with open("generated_glosses.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Input", "Generated Gloss"])

    for line in lines:
        inputs = tokenizer(line, return_tensors="pt", truncation=True, padding=True).to(model.device)
        output_ids = model.generate(**inputs, max_length=128)
        gloss = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        writer.writerow([line, gloss])
