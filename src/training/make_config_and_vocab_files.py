# make_config_and_vocab_files.py
import json, torch

pt_path   = "transformer_model.pt"
vocab_src = "transformer_model.pt.vocab.json"

ckpt = torch.load(pt_path, map_location="cpu")
with open("transformer_model_config.json", "w") as f:
    json.dump(ckpt["config"], f, indent=2)

with open(vocab_src) as f:
    V = json.load(f)

out = {
  "text_vocab": V["text_vocab"],
  "gloss_vocab": V["gloss_vocab"],
  "text_word_to_index": V["text_word_to_index"],
  "gloss_word_to_index": V["gloss_word_to_index"],
}
with open("transformer_vocab.json", "w") as f:
    json.dump(out, f, indent=2)

print("Wrote transformer_model_config.json and transformer_vocab.json")
