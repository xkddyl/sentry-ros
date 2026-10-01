"""Reference BEV + Transformer policy.

The network outputs normalized [vx, vy, wz] in [-1, 1]. Physical limits are
applied outside the model through training.end_to_end.contract.
"""

from __future__ import annotations

import torch
from torch import nn


class BevTransformerPolicy(nn.Module):
    def __init__(
        self,
        *,
        in_channels: int = 6,
        bev_height: int = 128,
        bev_width: int = 128,
        state_dim: int = 5,
        patch_size: int = 8,
        embed_dim: int = 256,
        transformer_layers: int = 4,
        attention_heads: int = 8,
        mlp_ratio: float = 4.0,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        if bev_height % patch_size or bev_width % patch_size:
            raise ValueError("BEV dimensions must be divisible by patch_size")
        if embed_dim % attention_heads:
            raise ValueError("embed_dim must be divisible by attention_heads")

        self.patch_embed = nn.Conv2d(
            in_channels,
            embed_dim,
            kernel_size=patch_size,
            stride=patch_size,
        )
        token_count = (bev_height // patch_size) * (bev_width // patch_size)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
        self.positional_embedding = nn.Parameter(
            torch.zeros(1, token_count + 1, embed_dim)
        )

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=attention_heads,
            dim_feedforward=int(embed_dim * mlp_ratio),
            dropout=dropout,
            batch_first=True,
            norm_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=transformer_layers,
        )
        self.state_encoder = nn.Sequential(
            nn.Linear(state_dim, embed_dim),
            nn.GELU(),
            nn.LayerNorm(embed_dim),
        )
        self.action_head = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),
            nn.GELU(),
            nn.LayerNorm(embed_dim),
            nn.Linear(embed_dim, 3),
            nn.Tanh(),
        )

        nn.init.normal_(self.cls_token, std=0.02)
        nn.init.normal_(self.positional_embedding, std=0.02)

    def forward(self, bev: torch.Tensor, state: torch.Tensor) -> torch.Tensor:
        if bev.ndim != 4:
            raise ValueError("bev must have shape [B, C, H, W]")
        if state.ndim != 2:
            raise ValueError("state must have shape [B, state_dim]")
        if bev.shape[0] != state.shape[0]:
            raise ValueError("bev and state batch sizes must match")

        tokens = self.patch_embed(bev).flatten(2).transpose(1, 2)
        cls = self.cls_token.expand(bev.shape[0], -1, -1)
        tokens = torch.cat((cls, tokens), dim=1)
        if tokens.shape[1] != self.positional_embedding.shape[1]:
            raise ValueError(
                "input BEV size does not match the configured positional embedding"
            )

        encoded = self.encoder(tokens + self.positional_embedding)
        bev_feature = encoded[:, 0]
        state_feature = self.state_encoder(state)
        return self.action_head(torch.cat((bev_feature, state_feature), dim=-1))
