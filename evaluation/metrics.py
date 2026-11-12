"""Small metric helpers (no scikit-learn needed)."""
from typing import Dict, Iterable, List, Sequence, Tuple

SEVERITIES = ["CRITICAL", "HIGH", "MODERATE", "LOW"]


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    p, r = safe_div(tp, tp + fp), safe_div(tp, tp + fn)
    return p, r, safe_div(2 * p * r, p + r)


def confusion(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str] = SEVERITIES) -> Dict[str, Dict[str, int]]:
    cm = {g: {p: 0 for p in labels} for g in labels}
    for g, p in zip(gold, pred):
        cm[g][p] += 1
    return cm


def per_class(cm: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, float]]:
    out = {}
    for lab in cm:
        tp = cm[lab][lab]
        fp = sum(cm[g][lab] for g in cm if g != lab)
        fn = sum(cm[lab][p] for p in cm[lab] if p != lab)
        p, r, f = prf(tp, fp, fn)
        out[lab] = {"precision": p, "recall": r, "f1": f, "support": tp + fn}
    return out


def macro(pc: Dict[str, Dict[str, float]], key: str) -> float:
    vals = [v[key] for v in pc.values() if v["support"] > 0]
    return sum(vals) / len(vals) if vals else 0.0


def set_micro_prf(golds: Iterable[Iterable[str]], preds: Iterable[Iterable[str]]) -> Tuple[float, float, float]:
    """Micro-averaged precision/recall/F1 over sets (e.g. requested resource items)."""
    tp = fp = fn = 0
    for g, p in zip(golds, preds):
        g, p = set(g), set(p)
        tp += len(g & p)
        fp += len(p - g)
        fn += len(g - p)
    return prf(tp, fp, fn)


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * q / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def summarize(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"n": 0, "mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    return {"n": len(values), "mean": sum(values) / len(values), "median": percentile(values, 50),
            "p95": percentile(values, 95), "max": max(values)}


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def md_table(header: List[str], rows: List[List[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)
