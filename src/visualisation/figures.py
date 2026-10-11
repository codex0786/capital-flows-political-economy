"""Publication figures (protocol Part VIII). Each figure is saved as PDF, SVG and PNG with its
source data as CSV in results/figures/data/. Footnotes state definitions, sample, units and
sources. Colours: validated categorical slots (blue, orange, aqua); aqua is below 3:1
contrast, so series are always direct-labelled and the data table is saved alongside.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.common import FIGURES, PROCESSED, TABLES, load_config

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
CFG = load_config()
SRC_BOP = "IMF BOP (IMF.STA:BOP v21, retrieved 2026-10-11); GDP: IMF WEO via DataMapper."

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": SURF, "axes.facecolor": SURF,
    "lines.linewidth": 2, "axes.titleweight": "bold", "axes.titlesize": 10, "axes.titlecolor": INK,
})


def save(fig, name, data: pd.DataFrame, note: str):
    (FIGURES / "data").mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.09, 1, 0.97))
    fig.text(0.01, 0.005, note, ha="left", va="bottom", fontsize=6.5, color=INK2, wrap=True)
    for ext in ("pdf", "svg", "png"):
        fig.savefig(FIGURES / f"{name}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    data.to_csv(FIGURES / "data" / f"{name}.csv", index=False)


def load():
    A = pd.read_parquet(PROCESSED / "annual_country_panel.parquet")
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet")
    return A, Q


def label_end(ax, x, y, text, color):
    """Direct end-label; nudges vertically away from labels already placed on this axis."""
    placed = getattr(ax, "_end_labels", [])
    span = np.diff(ax.get_ylim())[0] if ax.has_data() else 1.0
    ly = y
    for _ in range(20):
        clash = [p for p in placed if abs(p - ly) < 0.06 * span]
        if not clash:
            break
        ly = max(clash) + 0.06 * span if ly >= np.mean(clash) else min(clash) - 0.06 * span
    placed.append(ly)
    ax._end_labels = placed
    ax.annotate(text, (x, ly), xytext=(5, 0), textcoords="offset points", va="center", fontsize=8, color=INK,
                annotation_clip=False)
    ax.plot([x], [y], "o", ms=4, color=color)


# 1 ------------------------------------------------------------------ global trends by component
def fig1_trends(A):
    a = A[A.year.between(2015, 2025)]
    rows = []
    for (g, y), d in a.groupby(["country_group", "year"]):
        gdp = d.gdp_usd.sum()
        for c, lab in (("fdi_in_usd", "FDI"), ("port_in_usd", "Portfolio"), ("oi_in_usd", "Other investment")):
            dd = d.dropna(subset=[c])
            rows.append({"group": g, "year": y, "component": lab,
                         "pct_gdp": 100 * dd[c].sum() / dd.gdp_usd.sum(), "countries": dd.iso3.nunique()})
    t = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, g in zip(axes, ["AE", "EMDE"]):
        for comp, col in (("FDI", BLUE), ("Portfolio", ORANGE), ("Other investment", AQUA)):
            s = t[(t.group == g) & (t.component == comp)]
            ax.plot(s.year, s.pct_gdp, color=col)
            label_end(ax, s.year.iloc[-1], s.pct_gdp.iloc[-1], comp, col)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_title({"AE": "Advanced economies", "EMDE": "Emerging & developing economies"}[g])
        ax.set_xlim(2014.6, 2027.6)
        ax.set_xticks(range(2015, 2026, 2))
    axes[0].set_ylabel("Gross inflows, % of group GDP")
    fig.suptitle("Figure 1. Gross capital inflows by component, 2015–2025", x=0.01, ha="left", fontweight="bold")
    save(fig, "fig01_global_trends", t,
         "Gross inflows = net incurrence of liabilities (BPM6). Aggregate flows / aggregate GDP of countries reporting the component. "
         f"Annual sample: {A.iso3.nunique()} economies (rule-based). 2026 excluded (partial year). Source: {SRC_BOP}")


# 2 ------------------------------------------------------------------ AE vs EMDE: inflows, outflows, volatility
def fig2_groups(Q):
    q = Q[Q.year.between(2015, 2025)].copy()
    q["t"] = pd.PeriodIndex(q.quarter, freq="Q").to_timestamp()
    m = q.groupby(["country_group", "t"]).agg(inflows=("gross_inflows_gdp_w", "median"),
                                              outflows=("gross_outflows_gdp_w", "median"),
                                              vol8=("gross_inflows_vol8", "median"),
                                              n=("iso3", "nunique")).reset_index()
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4))
    for ax, v, title in zip(axes, ["inflows", "outflows", "vol8"],
                            ["Median gross inflows", "Median gross outflows", "Median inflow volatility (8-qtr SD)"]):
        for g, col in (("AE", BLUE), ("EMDE", ORANGE)):
            s = m[m.country_group == g]
            ax.plot(s.t, s[v], color=col, lw=1.6)
            label_end(ax, s.t.iloc[-1], s[v].iloc[-1], g, col)
        ax.set_title(title)
        ax.axhline(0, color=INK2, lw=0.8) if v != "vol8" else None
        ax.tick_params(axis="x", labelrotation=0)
        ax.xaxis.set_major_locator(matplotlib.dates.YearLocator(3))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    axes[0].set_ylabel("% of GDP (annualised)")
    fig.suptitle("Figure 2. Advanced vs emerging/developing economies, quarterly, 2015Q1–2025Q4",
                 x=0.01, ha="left", fontweight="bold")
    save(fig, "fig02_ae_vs_emde", m,
         f"Cross-country medians each quarter. Flows: 100×4×quarterly flow / annual GDP, winsorised 1/99. "
         f"Quarterly sample: {Q.iso3.nunique()} economies (AE {Q[Q.country_group=='AE'].iso3.nunique()}, "
         f"EMDE {Q[Q.country_group=='EMDE'].iso3.nunique()}). Source: {SRC_BOP}")


# 3 ------------------------------------------------------------------ composition by period
def fig3_composition(A):
    a = A[A.year.between(2015, 2025)].copy()
    a["period"] = pd.cut(a.year, [2014, 2019, 2021, 2025], labels=["2015–19", "2020–21", "2022–25"])
    comps = {"fdi_in_usd": "FDI", "pe_in_usd": "Portfolio equity", "pd_in_usd": "Portfolio debt", "oi_in_usd": "Other investment"}
    rows = []
    for (g, p), d in a.groupby(["country_group", "period"], observed=True):
        for c, lab in comps.items():
            dd = d.dropna(subset=[c])
            rows.append({"group": g, "period": str(p), "component": lab, "pct_gdp": 100 * dd[c].sum() / dd.gdp_usd.sum()})
    t = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6), sharey=True)
    cols = [BLUE, ORANGE, AQUA, "#4a3aa7"]
    for ax, g in zip(axes, ["AE", "EMDE"]):
        s = t[t.group == g]
        periods = ["2015–19", "2020–21", "2022–25"]
        w = 0.19
        for i, (lab, col) in enumerate(zip(comps.values(), cols)):
            vals = [s[(s.period == p) & (s.component == lab)].pct_gdp.iloc[0] for p in periods]
            xs = np.arange(3) + (i - 1.5) * (w + 0.02)
            ax.bar(xs, vals, width=w, color=col, label=lab)
        ax.set_xticks(range(3), periods)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_title({"AE": "Advanced economies", "EMDE": "Emerging & developing economies"}[g])
    axes[0].set_ylabel("Gross inflows, % of group GDP")
    axes[1].legend(frameon=False, fontsize=7.5, loc="upper right")
    fig.suptitle("Figure 3. Composition of gross inflows by period", x=0.01, ha="left", fontweight="bold")
    save(fig, "fig03_composition", t,
         "Aggregate component flow / aggregate GDP of reporting economies, by period. Portfolio split into equity & investment-fund shares (F5) "
         f"and debt securities (F3). Other investment includes official-sector liabilities. Source: {SRC_BOP}")


# 4 ------------------------------------------------------------------ event timelines (rule-selected countries)
def fig4_timelines(Q):
    pe = pd.read_csv(PROCESSED / "political_events.csv")
    el = pe[pe.event_type.str.startswith("election") & (pe.exec_relevant == 1) &
            pe.verification_status.isin(["wikipedia+idea+vdem", "two_sources"])]
    A = pd.read_parquet(PROCESSED / "annual_country_panel.parquet")
    g14 = A[A.year == 2014].set_index("iso3")
    qs = Q.iso3.unique()
    pick = []
    for g in ["AE", "EMDE"]:
        c = g14[(g14.country_group == g) & g14.index.isin(qs)].gdp_usd.sort_values(ascending=False)
        pick += list(c.index[:3])
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 6.0))
    out = []
    for ax, iso in zip(axes.flat, pick):
        s = Q[(Q.iso3 == iso) & (Q.year.between(2015, 2026))].copy()
        s["t"] = pd.PeriodIndex(s.quarter, freq="Q").to_timestamp()
        ax.plot(s.t, s.gross_inflows_gdp, color=BLUE, lw=1.4)
        ax.axhline(0, color=INK2, lw=0.8)
        e = el[el.iso3 == iso]
        for d, early in zip(pd.to_datetime(e.event_date), e.scheduled_or_unexpected):
            if pd.Timestamp("2015-01-01") <= d <= s.t.max() + pd.Timedelta(days=92):
                ax.axvline(d, color=ORANGE, lw=1, ls="-" if early == "scheduled_rule_based" else "--")
        ax.set_title(f"{s.country_name.iloc[0]} ({s.country_group.iloc[0]})")
        ax.xaxis.set_major_locator(matplotlib.dates.YearLocator(3))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
        out.append(s[["iso3", "quarter", "gross_inflows_gdp", "partial_year"]])
    for ax in axes[:, 0]:
        ax.set_ylabel("Gross inflows, % GDP (ann.)")
    fig.suptitle("Figure 4. Gross inflows and executive-relevant elections — three largest AEs and EMDEs in the quarterly sample (2014 GDP)",
                 x=0.01, ha="left", fontweight="bold", fontsize=9.5)
    save(fig, "fig04_event_timelines", pd.concat(out),
         "Blue: gross inflows (unwinsorised), 100×4×quarterly flow/annual GDP; 2026 quarters use WEO-projected GDP and are partial-year. "
         "Orange solid: scheduled election; dashed: early (rule-based). Countries chosen by rule (largest 2014 GDP), not by pattern. "
         "Elections: Wikipedia calendars corroborated by IDEA/V-Dem.")


# 5 ------------------------------------------------------------------ governance and flows
def fig5_governance(A):
    a = A[A.year.between(2015, 2025)]
    t = a.groupby("iso3").agg(rl=("wgi_rl_2014", "first"), inflows=("gross_inflows_gdp_w", "mean"),
                              group=("country_group", "first"), fc=("financial_centre", "first")).reset_index()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for g, col in (("AE", BLUE), ("EMDE", ORANGE)):
        s = t[(t.group == g) & (t.fc == 0)]
        ax.scatter(s.rl, s.inflows, s=22, color=col, edgecolor=SURF, linewidth=0.8, label=f"{g} ({len(s)})", zorder=3)
    f = t[t.fc == 1]
    ax.scatter(f.rl, f.inflows, s=26, facecolor="none", edgecolor=INK2, linewidth=1, label=f"Financial centres ({len(f)})", zorder=3)
    for r in f.itertuples():
        ax.annotate(r.iso3, (r.rl, r.inflows), xytext=(3, 2), textcoords="offset points", fontsize=6.5, color=INK2)
    ax.set_xlabel("WGI Rule of Law, 2014 (estimate)")
    ax.set_ylabel("Mean gross inflows 2015–25, % GDP")
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("Figure 5. Pre-sample rule of law and average gross inflows (descriptive)", loc="left")
    save(fig, "fig05_governance_flows", t,
         "Each dot is one economy. Descriptive cross-section; not a causal relationship (see Mundlak results). "
         "Inflows winsorised 1/99. Sources: World Bank WGI 2026 release; IMF BOP; IMF WEO.")


# 6 ------------------------------------------------------------------ institutional moderation
def fig6_moderation():
    me = pd.read_csv(TABLES / "h2_marginal_effects.csv")
    labels = {"wgi_rl_2014": "Rule of law (primary)", "wgi_rq_2014": "Regulatory quality", "wgi_ge_2014": "Gov. effectiveness",
              "wgi_va_2014": "Voice & accountability", "wgi_cc_2014": "Control of corruption", "wgi_pv_2014": "Political stability",
              "v2x_jucon_2014": "Judicial constraints (V-Dem)", "v2xlg_legcon_2014": "Legislative constraints (V-Dem)"}
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    y = 0
    ticks, names = [], []
    for m, lab in labels.items():
        s = me[me.moderator == m]
        for at, col, off in (("p10", ORANGE, 0.22), ("p50", INK2, 0), ("p90", BLUE, -0.22)):
            r = s[s["at"] == at].iloc[0]
            ax.errorbar(r.effect, y + off, xerr=[[r.effect - r.ci_low], [r.ci_high - r.effect]], fmt="o", ms=4,
                        color=col, ecolor=col, elinewidth=1.4, capsize=0)
        ticks.append(y)
        names.append(lab)
        y -= 1
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(ticks, names)
    ax.set_xlabel("Marginal effect of pre-election window on gross inflows (pp of GDP, annualised)")
    ax.text(0.0, 1.01, "orange = 10th percentile · grey = median · blue = 90th percentile of the moderator",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=7.5, color=INK2)
    fig.suptitle("Figure 6. Election-window effect at low, median and high institutional quality",
                 x=0.01, ha="left", fontweight="bold")
    save(fig, "fig06_institutional_moderation", me,
         "Two-way FE (country, quarter), lagged macro controls, 95% CIs clustered by country; moderators fixed at 2014 levels, centred. "
         "Rule of law is the pre-registered moderator (H2); the others are a secondary family (Holm-adjusted). 108 economies, 2015Q1–2025Q4.")


# 7 ------------------------------------------------------------------ event-study coefficients
def fig7_event_study():
    E = pd.read_csv(TABLES / "event_study_coefficients.csv")
    E = E[~E.k.astype(str).str.startswith("pre")].copy()
    E["k"] = E.k.astype(int)
    ref = CFG["elections"]["reference_period"]
    designs = ["TWFE, scheduled only", "TWFE, all executive-relevant"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for ax, y, title in zip(axes, ["gross_inflows_gdp_w", "gross_outflows_gdp_w"], ["Gross inflows", "Gross outflows"]):
        for d, col, off in zip(designs, [BLUE, ORANGE], [-0.12, 0.12]):
            s = E[(E.design == d) & (E.outcome == y)].sort_values("k")
            s = pd.concat([s, pd.DataFrame({"k": [ref], "coef": [0.0], "ci_low": [0.0], "ci_high": [0.0]})]).sort_values("k")
            ax.errorbar(s.k + off, s.coef, yerr=[s.coef - s.ci_low, s.ci_high - s.coef], fmt="o-", ms=3.5, lw=1.2,
                        color=col, elinewidth=1, capsize=0, label=d.replace("TWFE, ", ""))
        ax.axhline(0, color=INK, lw=0.8)
        ax.axvline(ref, color=INK2, lw=0.8, ls=":")
        ax.annotate("reference\n(k = −4)", (ref, ax.get_ylim()[1] * 0.85 if ax.get_ylim()[1] > 0 else 1), fontsize=6.5,
                    color=INK2, ha="center")
        ax.axvspan(-1.5, 0.5, color=GRID, alpha=0.5, lw=0)
        ax.set_title(title)
        ax.set_xlabel("Quarters relative to executive-relevant election")
        ax.set_xticks(range(-6, 7))
    axes[0].set_ylabel("pp of GDP (annualised), 95% CI")
    axes[1].legend(frameon=False, fontsize=7.5)
    fig.suptitle("Figure 7. Event-study coefficients around elections", x=0.01, ha="left", fontweight="bold")
    save(fig, "fig07_event_study", E,
         "TWFE with country and quarter FE, lagged macro controls; reference k = −4 and quarters > 6 from an election. Shaded = pre-registered pre-election window "
         "(k = −1, 0). CIs clustered by country. Stacked clean-control estimates are in results/tables/event_study_coefficients.csv.")


# 8 ------------------------------------------------------------------ external vulnerability
def fig8_vulnerability(Q):
    q = Q[Q.year.between(2015, 2025)]
    t = q.groupby("iso3").agg(sd=("gross_inflows_gdp_w", "std"), res=("reserves_months_2014", "first"),
                              std_=("st_debt_reserves_2014", "first"), group=("country_group", "first"),
                              fc=("financial_centre", "first")).reset_index()
    t = t[t.fc == 0]
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
    for ax, x, lab in ((axes[0], "res", "Reserves, months of imports (2014)"), (axes[1], "std_", "Short-term external debt, % of reserves (2014)")):
        for g, col in (("AE", BLUE), ("EMDE", ORANGE)):
            s = t[(t.group == g)].dropna(subset=[x])
            ax.scatter(s[x], s.sd, s=20, color=col, edgecolor=SURF, linewidth=0.8, label=f"{g} ({len(s)})")
        ax.set_xlabel(lab)
        ax.set_xscale("log")
    axes[0].set_ylabel("SD of quarterly gross inflows 2015–25\n(pp of GDP, annualised)")
    axes[0].legend(frameon=False, fontsize=7.5)
    axes[1].text(0.98, 0.95, "WDI reports ST debt for\nEMDE debtors only", transform=axes[1].transAxes, ha="right", va="top", fontsize=7, color=INK2)
    fig.suptitle("Figure 8. External buffers and inflow volatility (descriptive, financial centres excluded)", x=0.01, ha="left", fontweight="bold")
    save(fig, "fig08_external_vulnerability", t,
         "Log x-axes. Volatility = within-country SD of winsorised quarterly gross inflows. Sources: IMF BOP, World Bank WDI.")


# 9 ------------------------------------------------------------------ policy-event comparison (exploratory)
def fig9_policy(A):
    pev = pd.read_csv(PROCESSED / "policy_events.csv")
    ka = pev[pev.policy_domain == "capital_account"].copy()
    ka["year"] = ka.implementation_date.str[:4].astype(int)
    ka["dir"] = np.where(ka.exposure_definition.str.startswith("liberal"), "Liberalisation", "Tightening")
    a = A.set_index(["iso3", "year"]).gross_inflows_gdp_w
    rows = []
    for r in ka.itertuples():
        base = a.get((r.iso3, r.year - 1), np.nan)
        for k in range(-2, 3):
            v = a.get((r.iso3, r.year + k), np.nan)
            rows.append({"iso3": r.iso3, "event_year": r.year, "dir": r.dir, "k": k, "change_vs_tm1": v - base})
    t = pd.DataFrame(rows).dropna()
    m = t.groupby(["dir", "k"]).change_vs_tm1.agg(["mean", "sem", "count"]).reset_index()
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for d, col, off in (("Liberalisation", BLUE, -0.06), ("Tightening", ORANGE, 0.06)):
        s = m[m.dir == d]
        ax.errorbar(s.k + off, s["mean"], yerr=1.96 * s["sem"], fmt="o-", color=col, lw=1.4, ms=4, capsize=0,
                    label=f"{d} (n={int(s['count'].max())} events)")
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xticks(range(-2, 3))
    ax.set_xlabel("Years relative to KAOPEN change")
    ax.set_ylabel("Δ gross inflows vs t−1 (pp of GDP)")
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("Figure 9. Gross inflows around capital-account regime changes (exploratory)", loc="left")
    save(fig, "fig09_policy_events", m,
         "Events: |annual change in Chinn–Ito ka_open| ≥ 0.10, 2015–2023 (data-derived; not hand-coded). Means ±1.96 SE across events, "
         "no comparison group — descriptive only; capital-account policy is endogenous to flows.")


# 10 ------------------------------------------------------------------ robustness summary
def fig10_robustness():
    R = pd.read_csv(TABLES / "robustness_matrix.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 6), sharey=True)
    tests = R[R.outcome.isin(["gross_inflows_gdp_w", "gross_inflows_gdp", "y25", "y_prevgdp"])].test.unique().tolist()
    for ax, (outs, title) in zip(axes, [(["gross_inflows_gdp_w", "gross_inflows_gdp"], "Gross inflows"),
                                         (["gross_outflows_gdp_w", "gross_outflows_gdp"], "Gross outflows")]):
        first = R.iloc[: len(R) // 2] if title == "Gross inflows" else R.iloc[len(R) // 2:]
        for i, r in enumerate(first.itertuples()):
            for lab, col, off in (("pre", BLUE, 0.15), ("post", ORANGE, -0.15)):
                b, se = getattr(r, f"{lab}_coef"), getattr(r, f"{lab}_se")
                ax.errorbar(b, -i + off, xerr=1.96 * se, fmt="o", ms=3.5, color=col, elinewidth=1.2, capsize=0)
        ax.axvline(0, color=INK, lw=0.8)
        ax.set_yticks([-i for i in range(len(first))], first.test.tolist())
        ax.set_title(title)
        ax.set_xlabel("Coefficient (pp of GDP, annualised), 95% CI")
    fig.text(0.01, 0.955, "blue = pre-election window (primary, H1a/H1b) · orange = post-election window (secondary)",
             ha="left", fontsize=8, color=INK2)
    fig.suptitle("Figure 10. Pre-specified robustness tests for the election-window coefficients", x=0.01, ha="left", fontweight="bold")
    save(fig, "fig10_robustness", R,
         "Each row re-estimates the baseline (country & quarter FE, lagged controls, clustered by country unless stated). "
         "Threat addressed by each test: results/tables/robustness_matrix.csv.")


def main():
    A, Q = load()
    fig1_trends(A); fig2_groups(Q); fig3_composition(A); fig4_timelines(Q); fig5_governance(A)
    fig6_moderation(); fig7_event_study(); fig8_vulnerability(Q); fig9_policy(A); fig10_robustness()


if __name__ == "__main__":
    main()
