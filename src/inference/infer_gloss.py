# infer_gloss.py
import json, argparse, torch, os, sys
from src.training.t2g_model import TransformerModel

def pick_device(force_cpu=False):
    if force_cpu:
        return torch.device("cpu")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")

def load_all(model_path, config_path, vocab_path, device):
    with open(config_path) as f:
        config = json.load(f)
    with open(vocab_path) as f:
        v = json.load(f)

    text_word_to_index = v["text_word_to_index"]
    gloss_word_to_index = v["gloss_word_to_index"]
    gloss_index_to_word = {int(i): w for w, i in gloss_word_to_index.items()}

    pad_text = text_word_to_index["<pad>"]
    pad_gloss = gloss_word_to_index["<pad>"]

    model = TransformerModel(
        text_vocab_size=len(v["text_vocab"]),
        gloss_vocab_size=len(v["gloss_vocab"]),
        embedding_dim=config["embedding_dim"],
        nhead=config["nhead"],
        num_encoder_layers=config["num_encoder_layers"],
        num_decoder_layers=config["num_decoder_layers"],
        dropout=config["dropout"],
        max_len=config["max_len"],
        pad_index_text=pad_text,
        pad_index_gloss=pad_gloss
    ).to(device)

    state = torch.load(model_path, map_location=device)
    if isinstance(state, dict) and "model_state_dict" in state:
        state = state["model_state_dict"]
    model.load_state_dict(state)
    model.eval()
    return model, text_word_to_index, gloss_word_to_index, gloss_index_to_word

def tokenize_text(sentence, word_to_index, max_len=64):
    toks = sentence.lower().split()
    ids = [word_to_index.get(t, word_to_index["<unk>"]) for t in toks]
    ids = ids[:max_len] + [word_to_index["<pad>"]] * (max_len - len(ids))
    return torch.tensor(ids, dtype=torch.long)

@torch.no_grad()
def generate_translation(model, src, device, text_word_to_index, gloss_word_to_index, gloss_index_to_word, max_len=100):
    src = src.to(device)
    src_padding_mask = (src.unsqueeze(0) == text_word_to_index["<pad>"]).to(device)

    src_embedded = model.positional_encoding(model.text_embedding(src.unsqueeze(0)))
    memory = model.transformer.encoder(src_embedded, src_key_padding_mask=src_padding_mask)

    ys = torch.tensor([[gloss_word_to_index["<start>"]]], device=device)
    for _ in range(max_len):
        tgt_mask = TransformerModel.generate_square_subsequent_mask(ys.size(1), device=device)
        tgt_padding_mask = torch.zeros(1, ys.size(1), dtype=torch.bool, device=device)

        tgt_embedded = model.positional_encoding(model.gloss_embedding(ys))
        out = model.transformer.decoder(
            tgt_embedded, memory,
            tgt_mask=tgt_mask,
            tgt_key_padding_mask=tgt_padding_mask,
            memory_key_padding_mask=src_padding_mask
        )
        logits = model.fc_out(out[:, -1])
        next_word = torch.argmax(logits, dim=1).item()
        if next_word == gloss_word_to_index["<end>"]:
            break
        ys = torch.cat([ys, torch.tensor([[next_word]], device=device)], dim=1)

    toks = []
    for idx in ys[0][1:]:
        tok = gloss_index_to_word[idx.item()]
        if tok == "<end>":
            break
        toks.append(tok)
    return " ".join(toks)

def run_one(model, device, tw2i, gw2i, gi2w, text, max_src_len, max_len):
    src = tokenize_text(text, tw2i, max_len=max_src_len)
    return generate_translation(model, src, device, tw2i, gw2i, gi2w, max_len=max_len)

def main():
    ap = argparse.ArgumentParser(description="Text → Gloss inference (single or file)")
    ap.add_argument("--model",  default="transformer_model.pt")
    ap.add_argument("--config", default="transformer_model_config.json")
    ap.add_argument("--vocab",  default="transformer_vocab.json")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="Single input sentence")
    g.add_argument("--file", help="Path to text file (one sentence per line)")
    ap.add_argument("--output", help="If set in file mode, save results here")
    ap.add_argument("--max_src_len", type=int, default=64)
    ap.add_argument("--max_len",     type=int, default=100)
    ap.add_argument("--cpu", action="store_true")
    args = ap.parse_args()

    device = pick_device(force_cpu=args.cpu)
    model, tw2i, gw2i, gi2w = load_all(args.model, args.config, args.vocab, device)

    if args.text:
        print(run_one(model, device, tw2i, gw2i, gi2w, args.text, args.max_src_len, args.max_len))
        return

    # file mode
    if not os.path.exists(args.file):
        print(f"File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "r") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    results = []
    for ln in lines:
        gloss = run_one(model, device, tw2i, gw2i, gi2w, ln, args.max_src_len, args.max_len)
        line_out = f"{ln}  -->  {gloss}"
        results.append(line_out)
        print(line_out)

    if args.output:
        with open(args.output, "w") as out_f:
            out_f.write("\n".join(results))
        print(f"\n✅ Translations saved to: {os.path.abspath(args.output)}")

if __name__ == "__main__":
    main()
