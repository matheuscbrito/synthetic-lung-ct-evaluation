"""Experimento B — assinatura de ruído nos quatro conjuntos com uma calibração congelada.

Uso (da raiz do repositório):

    .venv/bin/python -m frameworks.noise_signature.experimentos.avaliar_datasets \\
        --output-dir resultados/ruido_datasets

1. Calibra uma vez nas originais válidas do Dsr (as reais são idênticas nos
   conjuntos) e congela: noise_signature, texture_evaluator e noise_evaluator.
2. Avalia Dsr, Dsr-baseline e Dsr-gpbo11 (mesma anatomia) e Dgen (só máscara),
   sempre com as máscaras do Dgen.
3. Contagens por conjunto e técnica; mediana do z por métrica com IC 95% por
   bootstrap dos cortes; métricas que mais derrubam.
4. Baseline × gpbo11 pareados por corte (Wilcoxon no |z|).
5. Concordância com o noise_evaluator (Lucas): tabela cruzada e kappa de Cohen;
   e cruzamento com a textura (o ruído acrescenta informação?).
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

from frameworks.noise_evaluator.integration import NOISE_READINGS, calibrate_nps, evaluate_nps_pair, noise_statuses
from frameworks.noise_signature import evaluate as ns_eval
from frameworks.noise_signature.nps import ROI_SIZE, SKIP_BINS, frequencies
from frameworks.texture_evaluator.regional import apply_pair_check

from .ortogonalidade import (DATE, DGEN, FLAGGED, NOISE_TECHS, SEED, STATUS_COLORS, STATUS_ORDER, dump_json, evaluate_noise,
                             fmt_counts, fnum, load_reference, md_table, metric_keys, pct_flagged, plt_setup, pt, status_bars,
                             texture_row, worst_abs_z, write_csv)

DATASETS = {"Dsr": (Path("dados/Dsr"), True), "Dsr-baseline": (Path("dados/Dsr-baseline"), True),
            "Dsr-gpbo11": (Path("dados/Dsr-gpbo11"), True), "Dgen": (Path("dados/Dgen"), False)}
DATASET_COLORS = {"Dsr": "#2a78d6", "Dsr-baseline": "#eb6834", "Dsr-gpbo11": "#1baf7a", "Dgen": "#eda100"}
BOOT = 2000


def evaluate_dataset(name, data_dir, same_anatomy, calib, ctx, nps_ref):
    valid, rejected = ns_eval.load_valid(data_dir, DGEN)
    rows, profiles = [], []
    texture_rows = []
    for case in valid:
        noise, (real, gen) = evaluate_noise(case.paths.case_id, case.original, case.synthetic, case.lung_mask, case.lung_mask, calib, same_anatomy)
        tex = texture_row(case.paths.case_id, case.original, case.synthetic, case.lung_mask, ctx)
        texture_rows.append(tex)
        lucas = evaluate_nps_pair(case.original, case.synthetic, case.lung_mask, nps_ref)
        lucas_st = noise_statuses(lucas)
        row = {"dataset": name, **noise,
               "tex_GLCM": tex["tex_GLCM"], "tex_Wavelet": tex["tex_Wavelet"], "tex_NEx": tex["tex_NEx"],
               "tex_textura": tex["tex_textura"], "tex_brilho": tex["tex_brilho"],
               "lucas_verdict": lucas["nps_verdict"], **{f"lucas_{k}": lucas_st[v] for k, v in NOISE_READINGS.items()},
               **{f"lucas_{k}": lucas.get(f"nps_{k}") for k in ("roi_count", "quantity_z", "grain_z", "low_band_z", "high_band_z", "quantity_pct", "air_excess")}}
        rows.append(row)
        prof = {}
        for region in ("lung", "soft"):
            for side, reading in (("real", real), ("synthetic", gen)):
                p = reading[f"t1_{region}"]["roi"]["profile"]
                prof[f"{region}_{side}"] = p.mean(axis=0) if len(p) else None
        profiles.append(prof)
        print(f"[{name}] {case.paths.case_id}: {noise['noise_signature_status']} · Lucas {lucas['nps_verdict']} · textura {tex['tex_textura']}", flush=True)
    mode = apply_pair_check(texture_rows)
    for row, tex in zip(rows, texture_rows):
        row["tex_final"] = tex["final_status"]
        row["tex_pair_mode"] = mode
    return rows, profiles, valid, rejected


def boot_median_ci(values, rng, draws=BOOT):
    values = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if values.size < 3:
        return float(np.median(values)) if values.size else float("nan"), float("nan"), float("nan"), int(values.size)
    med = np.median(rng.choice(values, (draws, values.size), replace=True), axis=1)
    lo, hi = np.percentile(med, [2.5, 97.5])
    return float(np.median(values)), float(lo), float(hi), int(values.size)


def kappa(a, b) -> float:
    labels = sorted(set(a) | set(b))
    n = len(a)
    if not n:
        return float("nan")
    po = np.mean([x == y for x, y in zip(a, b)])
    pe = sum((sum(x == l for x in a) / n) * (sum(y == l for y in b) / n) for l in labels)
    return float((po - pe) / (1 - pe)) if pe < 1 else float("nan")


def crosstab(a, b, la, lb):
    rows_l = [s for s in STATUS_ORDER if s in set(a)] + sorted(set(a) - set(STATUS_ORDER))
    cols_l = [s for s in STATUS_ORDER if s in set(b)] + sorted(set(b) - set(STATUS_ORDER))
    c = Counter(zip(a, b))
    return {"rows": rows_l, "cols": cols_l, "table": [[c.get((r, k), 0) for k in cols_l] for r in rows_l], "row_label": la, "col_label": lb}


def crosstab_md(ct) -> str:
    return md_table([f"{ct['row_label']} \\ {ct['col_label']}"] + ct["cols"], [[r] + vals for r, vals in zip(ct["rows"], ct["table"])])


def binary(status) -> str:
    return "aprovada" if status in ("aprovada", "approved") else "não aprovada"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out, fig_dir = args.output_dir, args.output_dir / "figuras"
    fig_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    ref_valid, _, calib, ctx = load_reference()
    nps_ref = calibrate_nps(ref_valid, ctx.scale.as_dict())
    dump_json(out / "calibracao.json", {"noise_signature": calib, "noise_evaluator": nps_ref, "calibrado_em": "dados/Dsr (originais válidas)",
                                        "n_originais": len(ref_valid)})

    all_rows, profiles, protocol = [], {}, {}
    for name, (data_dir, same) in DATASETS.items():
        rows, prof, valid, rejected = evaluate_dataset(name, data_dir, same, calib, ctx, nps_ref)
        all_rows += rows
        profiles[name] = prof
        protocol[name] = {"data_dir": str(data_dir), "pair_mode": "same-anatomy" if same else "mask-only", "n_valid": len(valid),
                          "n_rejected": len(rejected),
                          "median_pair_correlation": float(np.median([fnum(r["pair_correlation"]) for r in rows]))}
    write_csv(out / "resultados.csv", all_rows)

    keys = metric_keys()
    by_ds = {name: [r for r in all_rows if r["dataset"] == name] for name in DATASETS}

    # 1. contagens, z por métrica, motivos
    status_summary, z_rows, driver_rows = {}, [], []
    for name, rows in by_ds.items():
        status_summary[name] = {
            "n": len(rows), "pair_mode": protocol[name]["pair_mode"],
            "ruido": dict(Counter(r["noise_signature_status"] for r in rows)),
            "ruido_1lado": dict(Counter(r["noise_status_1lado"] for r in rows)),
            **{t: dict(Counter(r[f"{t}_status"] for r in rows)) for t in NOISE_TECHS},
            **{f"{t}_1lado": dict(Counter(r[f"{t}_status_1lado"] for r in rows)) for t in NOISE_TECHS},
            "lucas": dict(Counter(r["lucas_verdict"] for r in rows)),
            "textura": dict(Counter(r["tex_textura"] for r in rows)),
            "textura_final": dict(Counter(r["tex_final"] for r in rows)),
        }
        for key in keys:
            med, lo, hi, n = boot_median_ci([fnum(r[f"{key}_z"]) for r in rows], rng)
            st = [r[f"{key}_status"] for r in rows]
            z_rows.append({"dataset": name, "metric": key, "median_z": med, "ci_low": lo, "ci_high": hi, "n": n,
                           "n_revisao": st.count("revisão"), "n_reprovada": st.count("reprovada"), "n_inconclusivo": st.count("inconclusivo")})
        # quem decide a técnica que reprova: para cada corte, as métricas com o pior status do corte
        drivers = Counter()
        for r in rows:
            worst = max((r[f"{k}_status"] for k in keys if r[f"{k}_status"] in FLAGGED), key=FLAGGED.index, default=None)
            if worst:
                drivers.update(k for k in keys if r[f"{k}_status"] == worst)
        driver_rows += [{"dataset": name, "metric": k, "n_cortes_decide": v} for k, v in drivers.most_common()]
    write_csv(out / "z_por_metrica.csv", z_rows)
    write_csv(out / "motivos.csv", driver_rows)

    # 2. baseline × gpbo11
    base = {r["case_id"]: r for r in by_ds["Dsr-baseline"]}
    gpbo = {r["case_id"]: r for r in by_ds["Dsr-gpbo11"]}
    common = sorted(set(base) & set(gpbo))
    cmp_rows = []
    summaries = {"pior |z| (todas as métricas)": lambda r: worst_abs_z(r, [f"{k}_z" for k in keys]),
                 "nº de métricas sinalizadas": lambda r: float(sum(r[f"{k}_status"] in FLAGGED for k in keys))}
    for key in keys:
        summaries[key] = (lambda k: lambda r: abs(fnum(r[f"{k}_z"])))(key)
    for label, fn in summaries.items():
        a = np.array([fn(base[c]) for c in common])
        b = np.array([fn(gpbo[c]) for c in common])
        ok = np.isfinite(a) & np.isfinite(b)
        diff = b[ok] - a[ok]
        p = float(wilcoxon(a[ok], b[ok]).pvalue) if ok.sum() >= 6 and np.any(diff != 0) else float("nan")
        cmp_rows.append({"medida": label, "n": int(ok.sum()), "mediana_baseline": float(np.median(a[ok])) if ok.any() else float("nan"),
                         "mediana_gpbo11": float(np.median(b[ok])) if ok.any() else float("nan"),
                         "mediana_diferenca": float(np.median(diff)) if ok.any() else float("nan"),
                         "gpbo11_melhor_em": int(np.sum(diff < 0)), "gpbo11_pior_em": int(np.sum(diff > 0)), "p_wilcoxon": p})
    write_csv(out / "baseline_vs_gpbo11.csv", cmp_rows)
    ct_bg = crosstab([base[c]["noise_signature_status"] for c in common], [gpbo[c]["noise_signature_status"] for c in common], "baseline", "gpbo11")
    ct_bg1 = crosstab([base[c]["noise_status_1lado"] for c in common], [gpbo[c]["noise_status_1lado"] for c in common], "baseline (1 lado)", "gpbo11 (1 lado)")

    # 3. Lucas e textura
    agree = {}
    for name, rows in by_ds.items():
        ours, ours1, lucas = [r["noise_signature_status"] for r in rows], [r["noise_status_1lado"] for r in rows], [r["lucas_verdict"] for r in rows]
        tex = [r["tex_textura"] for r in rows]
        agree[name] = {
            "ct_lucas": crosstab(ours, lucas, "noise_signature", "noise_evaluator"),
            "ct_lucas_1lado": crosstab(ours1, lucas, "noise_signature (1 lado)", "noise_evaluator"),
            "kappa_3cat": kappa(ours, lucas), "kappa_3cat_1lado": kappa(ours1, lucas),
            "kappa_binario": kappa([binary(s) for s in ours], [binary(s) for s in lucas]),
            "kappa_binario_1lado": kappa([binary(s) for s in ours1], [binary(s) for s in lucas]),
            "concordancia_binaria_1lado": float(np.mean([binary(a) == binary(b) for a, b in zip(ours1, lucas)])),
            "lucas_leituras_sinalizadas": {k: int(sum(r[f"lucas_{k}"] in FLAGGED for r in rows)) for k in NOISE_READINGS},
            "ct_textura": crosstab(ours1, tex, "noise_signature (1 lado)", "textura (GLCM/Wavelet/NEx)"),
            "ruido_sinaliza_textura_aprova": int(sum(a in FLAGGED and t == "aprovada" for a, t in zip(ours1, tex))),
            "textura_sinaliza_ruido_aprova": int(sum(a == "aprovada" and t in FLAGGED for a, t in zip(ours1, tex))),
            "lucas_sinaliza_textura_aprova": int(sum(a in FLAGGED and t == "aprovada" for a, t in zip(lucas, tex))),
        }
    # métricas de mesma natureza: quantidade e grão (z de cada framework)
    pairs = {"quantidade: t1_soft_sigma × Lucas quantity": ("t1_soft_sigma_z", "lucas_quantity_z"),
             "quantidade: t3_lung_mad1 × Lucas quantity": ("t3_lung_mad1_z", "lucas_quantity_z"),
             "grão: t1_soft_f_avg × Lucas grain": ("t1_soft_f_avg_z", "lucas_grain_z"),
             "grão: t1_lung_f_avg × Lucas grain": ("t1_lung_f_avg_z", "lucas_grain_z")}
    from scipy.stats import spearmanr
    same_kind = {}
    for label, (a, b) in pairs.items():
        x = np.array([fnum(r[a]) for r in all_rows])
        y = np.array([fnum(r[b]) for r in all_rows])
        ok = np.isfinite(x) & np.isfinite(y)
        same_kind[label] = {"n": int(ok.sum()), "rho": float(spearmanr(x[ok], y[ok]).correlation) if ok.sum() > 5 else float("nan"),
                            "sinal_igual_pct": float(100 * np.mean(np.sign(x[ok]) == np.sign(y[ok]))) if ok.any() else float("nan")}
    disagreements = []
    for r in all_rows:
        if binary(r["noise_status_1lado"]) != binary(r["lucas_verdict"]):
            flagged_lucas = [k for k in NOISE_READINGS if r[f"lucas_{k}"] in FLAGGED]
            ours = sorted(((abs(fnum(r[f"{k}_z"])), k) for k in keys if r[f"{k}_status"] in FLAGGED), reverse=True)[:3]
            disagreements.append({"dataset": r["dataset"], "case_id": r["case_id"], "noise_signature_1lado": r["noise_status_1lado"],
                                  "lucas": r["lucas_verdict"], "lucas_sinalizou": ", ".join(flagged_lucas),
                                  "nosso_top3": ", ".join(f"{k} (|z| {z:.1f})" for z, k in ours)})
    write_csv(out / "discordancias_lucas.csv", disagreements)

    # figuras
    groups = {}
    for name in DATASETS:
        groups[f"{name} · ruído"] = status_summary[name]["ruido"]
        groups[f"{name} · ruído (1 lado)"] = status_summary[name]["ruido_1lado"]
        groups[f"{name} · Lucas"] = status_summary[name]["lucas"]
        groups[f"{name} · textura"] = status_summary[name]["textura"]
    status_bars(fig_dir / "status_por_conjunto.png", groups, "Veredito por conjunto (calibração congelada nas reais do Dsr)")
    tech_groups = {f"{name} · {t.upper()}": status_summary[name][f"{t}_1lado"] for name in DATASETS for t in NOISE_TECHS}
    status_bars(fig_dir / "status_por_tecnica.png", tech_groups, "Status por técnica de ruído (shape_dist 1 lado)")

    plt = plt_setup()
    fig, ax = plt.subplots(figsize=(9, 0.55 * len(keys) + 1.5))
    width = 0.8 / len(DATASETS)
    for d, name in enumerate(DATASETS):
        data = [[np.clip(fnum(r[f"{k}_z"]), -10, 10) for r in by_ds[name] if np.isfinite(fnum(r[f"{k}_z"]))] for k in keys]
        pos = [i + (d - (len(DATASETS) - 1) / 2) * width for i in range(len(keys))]
        idx = [i for i, v in enumerate(data) if v]
        bp = ax.boxplot([data[i] for i in idx], positions=[pos[i] for i in idx], widths=width * 0.85, vert=False, patch_artist=True,
                        showfliers=False, medianprops={"color": "#0b0b0b", "lw": 1})
        for box in bp["boxes"]:
            box.set(facecolor=DATASET_COLORS[name], edgecolor="white", alpha=0.9)
        ax.plot([], [], color=DATASET_COLORS[name], lw=6, label=f"{name} ({len(by_ds[name])})")
    for edge in (-2, -1, 1, 2):
        ax.axvline(edge, color="#a3a29b", lw=0.8, ls="--" if abs(edge) == 1 else ":")
    ax.axvline(0, color="#52514e", lw=0.8)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels(keys, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(-10, 10)
    ax.set_xlabel("z = (sintética − real) / IQR das reais (cortado em ±10; sem pontos extremos)")
    ax.legend(fontsize=8, frameon=False, ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.set_title("z por métrica de ruído e conjunto", fontsize=10, loc="left", pad=22)
    fig.tight_layout()
    fig.savefig(fig_dir / "z_por_metrica.png", dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(2, len(DATASETS), figsize=(3.2 * len(DATASETS), 6), sharey="row")
    for col, name in enumerate(DATASETS):
        for row_i, region in enumerate(("lung", "soft")):
            ax = axes[row_i, col]
            freqs = frequencies(ROI_SIZE[region])[SKIP_BINS:]
            for side, color, label in (("real", "#2a78d6", "real"), ("synthetic", "#eb6834", "sintética")):
                curves = [p[f"{region}_{side}"] for p in profiles[name] if p[f"{region}_{side}"] is not None]
                if curves:
                    c = np.array(curves)[:, SKIP_BINS:]
                    ax.semilogy(freqs, np.median(c, axis=0), color=color, lw=2, label=f"{label} (n={len(curves)})")
                    ax.fill_between(freqs, np.percentile(c, 25, axis=0), np.percentile(c, 75, axis=0), color=color, alpha=0.15, lw=0)
            ax.set_title(f"{name} · {'pulmão' if region == 'lung' else 'tecido mole'}", fontsize=9, loc="left")
            ax.legend(fontsize=7, frameon=False)
            if row_i == 1:
                ax.set_xlabel("ciclos/pixel")
            if col == 0:
                ax.set_ylabel("NPS radial (mediana dos cortes; faixa P25–P75)")
    fig.tight_layout()
    fig.savefig(fig_dir / "nps_medio_por_conjunto.png", dpi=130)
    plt.close(fig)

    summary = {"data": DATE, "calibracao": {"dataset": "dados/Dsr", "n_originais": len(ref_valid), "sigma0": calib["sigma0"]},
               "protocolo": protocol, "status": status_summary, "baseline_vs_gpbo11": {"n_pares": len(common), "testes": cmp_rows,
                                                                                         "ct": ct_bg, "ct_1lado": ct_bg1},
               "lucas_e_textura": agree, "mesma_natureza_lucas": same_kind, "n_discordancias_lucas": len(disagreements),
               "motivos_top": {name: [d for d in driver_rows if d["dataset"] == name][:6] for name in DATASETS},
               "z_por_metrica": z_rows}
    dump_json(out / "resumo.json", summary)

    parts = ["## Tabelas geradas automaticamente", ""]
    parts.append(md_table(["Conjunto", "n", "Ruído", "Ruído (1 lado)", "Lucas", "Textura"],
                          [[n, s["n"], fmt_counts(s["ruido"]), fmt_counts(s["ruido_1lado"]), fmt_counts(s["lucas"]), fmt_counts(s["textura"])]
                           for n, s in status_summary.items()]))
    parts += ["", md_table(["Conjunto"] + [t.upper() for t in NOISE_TECHS],
                           [[n] + [fmt_counts(s[f"{t}_1lado"]) for t in NOISE_TECHS] for n, s in status_summary.items()])]
    parts += ["", md_table(["Conjunto", "métrica", "mediana z", "IC 95%", "rev", "repr", "inc"],
                           [[z["dataset"], z["metric"], pt(z["median_z"], 2), f"{pt(z['ci_low'], 2)} a {pt(z['ci_high'], 2)}",
                             z["n_revisao"], z["n_reprovada"], z["n_inconclusivo"]] for z in z_rows])]
    parts += ["", md_table(list(cmp_rows[0].keys()), [[pt(v, 3) if isinstance(v, float) else v for v in r.values()] for r in cmp_rows])]
    parts += ["", crosstab_md(ct_bg), "", crosstab_md(ct_bg1)]
    for name, a in agree.items():
        parts += ["", f"### {name}", crosstab_md(a["ct_lucas"]), "", crosstab_md(a["ct_lucas_1lado"]), "", crosstab_md(a["ct_textura"]),
                  "", str({k: v for k, v in a.items() if not k.startswith("ct_")})]
    parts += ["", str(same_kind), "", str({n: [d for d in driver_rows if d["dataset"] == n][:8] for n in DATASETS})]
    (out / "tabelas_auto.md").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"pronto: {out}")


if __name__ == "__main__":
    main()
