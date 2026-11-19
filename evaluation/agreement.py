"""Inter-annotator agreement between the dataset labels and a second annotator's CSV.

    python -m evaluation.agreement evaluation/annotation/annotator2_labels.csv

Prints raw agreement, Cohen's kappa and linearly weighted kappa for severity, exact agreement for the
casualty count, a confusion matrix, and the list of disagreements (to be adjudicated by two people).
"""
import collections
import csv
import sys

from evaluation.dataset import load

CLASSES = ["CRITICAL", "HIGH", "MODERATE", "LOW"]


def kappas(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = collections.Counter(a), collections.Counter(b)
    pe = sum(pa[c] / n * pb[c] / n for c in CLASSES)
    idx = {c: i for i, c in enumerate(CLASSES)}
    w = lambda x, y: abs(idx[x] - idx[y]) / (len(CLASSES) - 1)
    do = sum(w(x, y) for x, y in zip(a, b)) / n
    de = sum(pa[c1] / n * pb[c2] / n * w(c1, c2) for c1 in CLASSES for c2 in CLASSES)
    return po, (po - pe) / (1 - pe), 1 - do / de


def main(path):
    gold = {s.id: s for s in load(original=True)}
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))[1:]
    lab = {int(r[0]): (r[2].strip().upper(), int(r[3])) for r in rows if r and r[0]}
    ids = sorted(gold)
    a, b = [gold[i].severity for i in ids], [lab[i][0] for i in ids]
    po, k, kw = kappas(a, b)
    print(f"{len(ids)} messages: agreement {po:.1%}, Cohen's kappa {k:.3f}, weighted kappa {kw:.3f}")
    cm = collections.Counter(zip(a, b))
    print("rows = dataset label, columns = second annotator")
    for r in CLASSES:
        print(f"{r:9}" + " ".join(f"{cm[(r, c)]:>4}" for c in CLASSES))
    print("casualty exact agreement", f"{sum(gold[i].casualties == lab[i][1] for i in ids) / len(ids):.1%}")
    for i in ids:
        if gold[i].severity != lab[i][0]:
            print(f"#{i}: {gold[i].severity} vs {lab[i][0]} | {gold[i].text}")


if __name__ == "__main__":
    main(sys.argv[1])
