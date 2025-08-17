# t2g_model.py
import math
import torch
import torch.nn as nn

class PositionalEncoding(nn.Module):
    def __init__(self, d_model, dropout=0.1, max_len=4096):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer('pe', pe)

    def forward(self, x):
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)

class TransformerModel(nn.Module):
    """
    Matches your training architecture, but avoids global variables by
    storing pad indices inside the model (safe for loading state_dict).
    """
    def __init__(
        self,
        text_vocab_size,
        gloss_vocab_size,
        embedding_dim,
        nhead,
        num_encoder_layers,
        num_decoder_layers,
        dropout,
        max_len,
        pad_index_text=0,
        pad_index_gloss=0
    ):
        super().__init__()
        self.text_embedding = nn.Embedding(text_vocab_size, embedding_dim)
        self.gloss_embedding = nn.Embedding(gloss_vocab_size, embedding_dim)
        self.positional_encoding = PositionalEncoding(embedding_dim, dropout, max_len)
        self.transformer = nn.Transformer(
            d_model=embedding_dim,
            nhead=nhead,
            num_encoder_layers=num_encoder_layers,
            num_decoder_layers=num_decoder_layers,
            dropout=dropout,
            batch_first=True
        )
        self.fc_out = nn.Linear(embedding_dim, gloss_vocab_size)
        # store pad ids (extra attributes won't affect state_dict loading)
        self.pad_index_text = pad_index_text
        self.pad_index_gloss = pad_index_gloss

    @staticmethod
    def generate_square_subsequent_mask(sz: int, device=None):
        # Boolean causal mask: True = disallow attending to future positions
        return torch.triu(
            torch.ones((sz, sz), dtype=torch.bool, device=device),
            diagonal=1
        )

    def _pad_mask_text(self, seq):
        return seq == self.pad_index_text  # (batch, seq)

    def _pad_mask_gloss(self, seq):
        return seq == self.pad_index_gloss  # (batch, seq)

    def forward(self, src, tgt):
        # masks
        src_padding_mask = self._pad_mask_text(src)
        tgt_in = tgt[:, :-1]
        tgt_padding_mask = self._pad_mask_gloss(tgt_in)
        tgt_mask = self.generate_square_subsequent_mask(tgt_in.size(1)).to(tgt.device)

        # embeddings
        src_emb = self.positional_encoding(self.text_embedding(src))
        tgt_emb = self.positional_encoding(self.gloss_embedding(tgt_in))

        out = self.transformer(
            src_emb, tgt_emb,
            tgt_mask=tgt_mask,
            src_key_padding_mask=src_padding_mask,
            tgt_key_padding_mask=tgt_padding_mask,
            memory_key_padding_mask=src_padding_mask
        )
        return self.fc_out(out)
