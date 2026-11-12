"""Triage evaluation: severity, casualties, resources and LOCATION accuracy on the labelled SOS set.

    python -m evaluation.eval_triage                 # rule-based parser, offline gazetteer (reproducible)
    python -m evaluation.eval_triage --online        # also use the OpenStreetMap geocoder
    python -m evaluation.eval_triage --mode gemini   # Gemini (needs GEMINI_API_KEY in .env)

Location outcomes are scored separately because a wrong pin is worse than no pin:
  correct / wrong_pin / missed          message names a gazetteer locality
  coords_ok / coords_bad                message contains coordinates
  correct_unresolved / false_pin        no place or outside Guwahati: it must NOT be pinned
  other_resolved / other_unresolved     real place not in the gazetteer (needs --online to resolve)
"""
import argparse
import collections
import json
import os
import time
from typing import Dict, List

from app import gazetteer
from app.config import Settings, get_settings
from app.geo import haversine_m
from app.triage import TriageError, resolve_location, rule_based_triage, run_triage
from evaluation.dataset import Sample, load
from evaluation.metrics import (SEVERITIES, confusion, macro, md_table, pct, per_class,
                                safe_div, set_micro_prf, summarize)

PLACE_TOLERANCE_M = 2000.0   # a pin within 2 km of the named locality counts as "the right place"
RESULTS = os.path.join(os.path.dirname(__file__), "results")


def score_location(s: Sample, res) -> Dict:
    resolved = res.location_source != "unknown" and res.latitude is not None
    out = {"resolved": resolved, "source": res.location_source, "uncertainty_m": res.uncertainty_m, "error_m": None}
    if s.place == "COORDS":
        if resolved:
            out["error_m"] = float(haversine_m(res.latitude, res.longitude, s.lat, s.lon))
            out["outcome"] = "coords_ok" if out["error_m"] < 50 else "coords_bad"
        else:
            out["outcome"] = "coords_bad"
    elif s.place in (None, "OUTSIDE"):
        out["outcome"] = "false_pin" if resolved else "correct_unresolved"
    elif s.place == "OTHER":
        out["outcome"] = "other_resolved" if resolved else "other_unresolved"
        if resolved and s.lat is not None:
            out["error_m"] = float(haversine_m(res.latitude, res.longitude, s.lat, s.lon))
    else:
        key, glat, glon, _ = gazetteer.lookup(s.place)
        if not resolved:
            out["outcome"] = "missed"
        else:
            out["error_m"] = float(haversine_m(res.latitude, res.longitude, glat, glon))
            out["outcome"] = "correct" if out["error_m"] <= PLACE_TOLERANCE_M else "wrong_pin"
    return out


def evaluate(mode: str, online: bool, limit: int = 0) -> Dict:
    data = load()[: limit or None]
    settings = Settings(geocode_online=online)
    key_settings = get_settings()
    rows: List[Dict] = []
    for s in data:
        t0 = time.perf_counter()
        parse_error = None
        try:
            parsed = rule_based_triage(s.text) if mode == "rules" else run_triage(s.text, settings=key_settings)
        except TriageError as exc:
            parse_error, parsed = str(exc), None
        if parsed is None:
            rows.append({"id": s.id, "text": s.text, "error": parse_error, "gold_severity": s.severity})
            continue
        res = resolve_location(parsed, settings=settings)
        ms = (time.perf_counter() - t0) * 1000
        rows.append({
            "id": s.id, "text": s.text, "latency_ms": ms,
            "gold_severity": s.severity, "pred_severity": parsed.severity,
            "gold_casualties": s.casualties, "pred_casualties": parsed.casualties,
            "gold_resources": sorted(s.resources), "pred_resources": sorted(r.item_name for r in parsed.needed_resources),
            "gold_place": s.place, "pred_location_text": parsed.location_text,
            "location": score_location(s, res),
        })

    ok = [r for r in rows if "pred_severity" in r]
    failed = [r for r in rows if "pred_severity" not in r]
    cm = confusion([r["gold_severity"] for r in ok], [r["pred_severity"] for r in ok])
    pc = per_class(cm)
    sev_acc = safe_div(sum(r["gold_severity"] == r["pred_severity"] for r in ok), len(rows))

    rank = {s: i for i, s in enumerate(SEVERITIES)}   # lower index = more urgent
    under = sum(rank[r["pred_severity"]] > rank[r["gold_severity"]] for r in ok)
    over = sum(rank[r["pred_severity"]] < rank[r["gold_severity"]] for r in ok)
    crit_missed = sum(r["gold_severity"] == "CRITICAL" and r["pred_severity"] != "CRITICAL" for r in ok)
    n_crit = sum(r["gold_severity"] == "CRITICAL" for r in rows)

    cas_err = [abs(r["pred_casualties"] - r["gold_casualties"]) for r in ok]
    rp, rr, rf = set_micro_prf([r["gold_resources"] for r in ok], [r["pred_resources"] for r in ok])

    outcomes = collections.Counter(r["location"]["outcome"] for r in ok)
    n_named = sum(outcomes[k] for k in ("correct", "wrong_pin", "missed"))
    n_nopin = sum(outcomes[k] for k in ("correct_unresolved", "false_pin"))
    coords_err = [r["location"]["error_m"] for r in ok if r["location"]["outcome"] in ("coords_ok", "coords_bad") and r["location"]["error_m"] is not None]
    place_err = [r["location"]["error_m"] for r in ok if r["location"]["outcome"] in ("correct", "wrong_pin")]
    unc = [r["location"]["uncertainty_m"] for r in ok if r["location"]["outcome"] == "correct" and r["location"]["uncertainty_m"] is not None]

    return {
        "mode": mode, "online_geocoding": online, "n_messages": len(rows), "n_parse_failures": len(failed),
        "severity": {"accuracy": sev_acc, "macro_precision": macro(pc, "precision"), "macro_recall": macro(pc, "recall"),
                     "macro_f1": macro(pc, "f1"), "per_class": pc, "confusion": cm,
                     "under_triage": under, "over_triage": over,
                     "critical_recall": safe_div(n_crit - crit_missed, n_crit), "critical_missed": crit_missed, "n_critical": n_crit},
        "casualties": {"exact_match": safe_div(sum(e == 0 for e in cas_err), len(cas_err)),
                       "within_1": safe_div(sum(e <= 1 for e in cas_err), len(cas_err)),
                       "mae": safe_div(sum(cas_err), len(cas_err))},
        "resources": {"precision": rp, "recall": rr, "f1": rf},
        "location": {"outcomes": dict(outcomes),
                     "named_place_accuracy": safe_div(outcomes["correct"], n_named),
                     "wrong_pin_rate_named": safe_div(outcomes["wrong_pin"], n_named),
                     "missed_rate_named": safe_div(outcomes["missed"], n_named),
                     "false_pin_rate_when_no_place_or_outside": safe_div(outcomes["false_pin"], n_nopin),
                     "coords_exact_rate": safe_div(outcomes["coords_ok"], outcomes["coords_ok"] + outcomes["coords_bad"]),
                     "coords_error_m": summarize(coords_err), "named_place_offset_m": summarize(place_err),
                     "reported_uncertainty_m_when_correct": summarize(unc),
                     "other_places_resolved": outcomes["other_resolved"], "other_places_total": outcomes["other_resolved"] + outcomes["other_unresolved"]},
        "latency_ms": summarize([r["latency_ms"] for r in ok]),
        "rows": rows,
    }


def to_markdown(res: Dict) -> str:
    sv, ca, rs, lo = res["severity"], res["casualties"], res["resources"], res["location"]
    o = lo["outcomes"]
    lines = [f"## Triage evaluation ({res['mode']} parser, online geocoding: {res['online_geocoding']})",
             f"{res['n_messages']} labelled messages; {res['n_parse_failures']} parse failures.", "",
             "### Severity",
             f"Accuracy **{pct(sv['accuracy'])}**, macro precision {pct(sv['macro_precision'])}, macro recall {pct(sv['macro_recall'])}, macro F1 {pct(sv['macro_f1'])}.", "",
             md_table(["Class", "Precision", "Recall", "F1", "Support"],
                      [[c, pct(v["precision"]), pct(v["recall"]), pct(v["f1"]), v["support"]] for c, v in sv["per_class"].items()]), "",
             f"Safety view: **CRITICAL recall {pct(sv['critical_recall'])}** ({sv['critical_missed']} of {sv['n_critical']} critical messages ranked lower). "
             f"Under-triaged (less urgent than truth): {sv['under_triage']}; over-triaged: {sv['over_triage']}.", "",
             "Confusion matrix (rows = truth, columns = predicted):", "",
             md_table(["truth \\ pred"] + SEVERITIES, [[g] + [sv["confusion"][g][p] for p in SEVERITIES] for g in SEVERITIES]), "",
             "### Casualty count and requested resources",
             f"Casualties: exact match {pct(ca['exact_match'])}, within +-1 {pct(ca['within_1'])}, mean absolute error {ca['mae']:.2f}. "
             f"Resource items: precision {pct(rs['precision'])}, recall {pct(rs['recall'])}, F1 {pct(rs['f1'])}.", "",
             "### Location",
             md_table(["Outcome", "Count"], [[k, v] for k, v in sorted(o.items())]), "",
             f"- Message names a gazetteer place: **correct {pct(lo['named_place_accuracy'])}**, wrong pin {pct(lo['wrong_pin_rate_named'])}, missed {pct(lo['missed_rate_named'])}.",
             f"- No place named or outside Guwahati: **false-pin rate {pct(lo['false_pin_rate_when_no_place_or_outside'])}** (target 0%).",
             f"- Coordinates in the message: exact (<50 m) {pct(lo['coords_exact_rate'])}.",
             f"- Places not in the gazetteer: {lo['other_places_resolved']} of {lo['other_places_total']} resolved "
             f"({'online geocoder on' if res['online_geocoding'] else 'online geocoder off, so unresolved is expected'}).",
             f"- Reported uncertainty when correct: median +-{lo['reported_uncertainty_m_when_correct']['median']:.0f} m.", "",
             f"### Latency per message (parse + locate): median {res['latency_ms']['median']:.2f} ms, p95 {res['latency_ms']['p95']:.2f} ms.", ""]
    bad = [r for r in res["rows"] if "pred_severity" in r and (r["gold_severity"] != r["pred_severity"] or r["location"]["outcome"] in ("wrong_pin", "missed", "false_pin", "coords_bad"))]
    lines.append(f"### Error analysis ({len(bad)} messages with a severity or location error)")
    for r in bad[:25]:
        lines.append(f"- #{r['id']} gold {r['gold_severity']} / predicted {r['pred_severity']}; location: {r['location']['outcome']}. \"{r['text'][:90]}\"")
    if len(bad) > 25:
        lines.append(f"- ... and {len(bad) - 25} more in the JSON file.")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["rules", "gemini"], default="rules")
    ap.add_argument("--online", action="store_true", help="use the OpenStreetMap geocoder")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    res = evaluate(a.mode, a.online, a.limit)
    os.makedirs(RESULTS, exist_ok=True)
    tag = f"triage_{a.mode}{'_online' if a.online else ''}"
    with open(os.path.join(RESULTS, tag + ".json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    md = to_markdown(res)
    with open(os.path.join(RESULTS, tag + ".md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
