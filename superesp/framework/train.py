"""superesp.framework.train — tiny CPU training + held-out evaluation.

Leak-free protocol: the caller passes pre-split train/val/test token tensors.
The tokenizer is fit on TRAIN only (see datasets/*), val is used for early model
selection, and ALL reported metrics come from the untouched TEST split.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import torch
from torch import Tensor

from superesp.framework.model import SuperESPHead


@dataclass
class TrainResult:
    model: SuperESPHead
    history: list[dict] = field(default_factory=list)
    best_val_acc: float = 0.0


def _accuracy(model: SuperESPHead, ids: Tensor, labels: Tensor) -> float:
    model.eval()
    with torch.no_grad():
        pred = model.forward(ids).argmax(dim=-1)
    return (pred == labels).float().mean().item()


def train_head(
    n_classes: int,
    train_ids: Tensor,
    train_labels: Tensor,
    val_ids: Tensor,
    val_labels: Tensor,
    *,
    epochs: int = 40,
    batch_size: int = 64,
    lr: float = 3e-3,
    weight_decay: float = 0.01,
    seed: int = 0,
    config=None,
) -> TrainResult:
    torch.manual_seed(seed)
    np.random.seed(seed)
    from superesp.framework.config import SHARED

    model = SuperESPHead(n_classes, config or SHARED)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)

    n = train_ids.shape[0]
    history: list[dict] = []
    best_val = 0.0
    best_state = {k: v.clone() for k, v in model.state_dict().items()}

    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(n)
        total_loss = 0.0
        for i in range(0, n, batch_size):
            idx = perm[i : i + batch_size]
            opt.zero_grad()
            loss = model.loss(train_ids[idx], train_labels[idx])
            loss.backward()
            opt.step()
            total_loss += loss.item() * len(idx)
        val_acc = _accuracy(model, val_ids, val_labels)
        history.append({"epoch": epoch, "loss": total_loss / n, "val_acc": val_acc})
        if val_acc >= best_val:
            best_val = val_acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)  # select best-on-val checkpoint
    return TrainResult(model=model, history=history, best_val_acc=best_val)


def train_regressor(
    train_ids: Tensor, train_y: Tensor, val_ids: Tensor, val_y: Tensor,
    *, epochs: int = 60, batch_size: int = 64, lr: float = 3e-3,
    weight_decay: float = 0.01, seed: int = 0, config=None,
) -> SuperESPHead:
    """Train a single-output regression head (MSE), select best-on-val (lowest val MSE)."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    from superesp.framework.config import SHARED
    model = SuperESPHead(1, config or SHARED, task="regress")
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    n = train_ids.shape[0]
    best_val = float("inf")
    best_state = {k: v.clone() for k, v in model.state_dict().items()}
    for _ in range(epochs):
        model.train()
        perm = torch.randperm(n)
        for i in range(0, n, batch_size):
            idx = perm[i:i + batch_size]
            opt.zero_grad()
            loss = model.loss(train_ids[idx], train_y[idx])
            loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            vmse = torch.nn.functional.mse_loss(
                model.forward(val_ids).squeeze(-1), val_y.float()).item()
        if vmse <= best_val:
            best_val = vmse
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    return model


def evaluate_regression(model: SuperESPHead, test_ids: Tensor,
                        test_y_real: np.ndarray, mean: float, std: float) -> dict:
    """Held-out RMSE/MAE/R² in ORIGINAL units; baseline = predict-the-mean."""
    model.eval()
    with torch.no_grad():
        pred_norm = model.forward(test_ids).squeeze(-1).numpy()
    pred = pred_norm * std + mean
    y = np.asarray(test_y_real, dtype=np.float64)
    err = pred - y
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mae = float(np.mean(np.abs(err)))
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) + 1e-9
    r2 = 1.0 - ss_res / ss_tot
    baseline_rmse = float(np.sqrt(np.mean((y - y.mean()) ** 2)))
    return {"rmse": rmse, "mae": mae, "r2": r2,
            "baseline_rmse": baseline_rmse, "n_test": int(len(y))}


def evaluate(model: SuperESPHead, test_ids: Tensor, test_labels: Tensor) -> dict:
    """Held-out TEST metrics. Returns accuracy + per-class confusion summary."""
    model.eval()
    with torch.no_grad():
        logits = model.forward(test_ids)
        probs = torch.softmax(logits, dim=-1)
        pred = logits.argmax(dim=-1)
    acc = (pred == test_labels).float().mean().item()
    n_classes = model.n_classes
    confusion = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(test_labels.tolist(), pred.tolist()):
        confusion[t][p] += 1
    return {
        "test_acc": acc,
        "n_test": int(test_labels.shape[0]),
        "confusion": confusion.tolist(),
        "probs": probs,
        "pred": pred,
        "labels": test_labels,
    }
