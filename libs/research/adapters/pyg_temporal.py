"""PyTorch Geometric Temporal adapter -- a GConvGRU over the fully connected symbol graph,
trained briefly to predict next returns from current ones; the training-loss trajectory
and the learned node embeddings are a REPRESENTATION of cross-asset structure.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pyg_temporal"
CAPABILITY_FAMILY = "graph_learning"
LICENCE_EXPECTED = "MIT"
MAX_SYMBOLS = 6
EPOCHS = 20
STEPS = 48


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    torch = A.library("torch")
    rec = A.library("torch_geometric_temporal.nn.recurrent")
    if torch is None or rec is None:
        return A.unmeasured(SYSTEM, bundle, "torch_geometric_temporal (or torch) is not "
                                            "importable here (pip install "
                                            "torch-geometric-temporal==0.56.2)")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 300][:MAX_SYMBOLS]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames long enough")
    n = min(len(f) for f in frames) - 1
    R = np.column_stack([f.log_returns()[-n:] for f in frames])
    R = R / np.maximum(R.std(axis=0, keepdims=True), 1e-12)
    k = R.shape[1]
    ei = torch.tensor([[i for i in range(k) for j in range(k) if i != j],
                       [j for i in range(k) for j in range(k) if i != j]], dtype=torch.long)
    try:
        torch.manual_seed(bundle.seed)
        model = rec.GConvGRU(in_channels=1, out_channels=8, K=2)
        head = torch.nn.Linear(8, 1)
        opt = torch.optim.Adam(list(model.parameters()) + list(head.parameters()), lr=0.01)
        losses: list[float] = []
        h = None
        for _ in range(EPOCHS):
            opt.zero_grad()
            total = torch.zeros(())
            h = None
            for t in range(n - 1 - STEPS, n - 1):
                x = torch.tensor(R[t], dtype=torch.float32).reshape(k, 1)
                y = torch.tensor(R[t + 1], dtype=torch.float32).reshape(k, 1)
                h = model(x, ei, H=h)
                total = total + torch.mean((head(h) - y) ** 2)
            total.backward()
            opt.step()
            losses.append(float(total.item()) / STEPS)
        emb = h.detach().numpy() if h is not None else np.zeros((k, 8))
    except Exception as exc:
        return A.packet(SYSTEM, bundle, trials=1, research_methods=[
            {"kind": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}])
    return A.packet(SYSTEM, bundle, trials=1, representations=[
        {"kind": "dynamic_graph_embedding", "symbols": [f.symbol for f in frames],
         "loss_first": losses[0], "loss_last": losses[-1], "epochs": EPOCHS,
         "node_embeddings": emb, "representation": "cross-asset state learned on a graph"}])


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
