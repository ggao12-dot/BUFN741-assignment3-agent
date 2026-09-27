"""Render the post-audit interim report from materialized empirical facts."""
from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

from src.utils.config import ROOT


FACTS_PATH = ROOT / "results/tables/interim_report/interim_empirical_facts.json"
REPORT_PATH = ROOT / "reports/assignment3_empirical_results_report.md"


def _find(records: list[dict], **keys) -> dict:
    matches = [row for row in records if all(row.get(key) == value for key, value in keys.items())]
    if len(matches) != 1:
        raise ValueError(f"Expected one record for {keys}, found {len(matches)}")
    return matches[0]


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|",
            *["| " + " | ".join(str(value) for value in row) + " |" for row in rows]]


def _pct(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}%"


def _fm_cell(facts: dict, universe: str, sample: str, spec: int, coefficient: str) -> str:
    rows = [r for r in facts["fm_all"] if r["universe"] == universe and r["sample"] == sample
            and r["specification"] == spec and r["coefficient"] == coefficient]
    if not rows:
        return "—"
    row = rows[0]
    return f"{row['mean_lambda_pct_month']:.3f} ({row['fm_t_stat']:.2f})"


def _fm_panel(facts: dict, universe: str, sample: str) -> list[str]:
    rows = []
    for spec in range(1, 9):
        rows.append([str(spec), *[_fm_cell(facts, universe, sample, spec, coefficient)
            for coefficient in ["intercept", "MKT", "SMB", "HML", "RMW", "CMA"]]])
    return _table(["Spec.", "Intercept", "MKT", "SMB", "HML", "RMW", "CMA"], rows)


def build_report(
    facts_path: Path = FACTS_PATH,
    report_path: Path = REPORT_PATH,
    canonical: bool = False,
) -> Path:
    facts = json.loads(facts_path.read_text())
    fit_e = _find(facts["mean_cross_family_fit"], sample="earlier")
    fit_p = _find(facts["mean_cross_family_fit"], sample="post_gfc")
    breadth_e = _find(facts["improvement_breadth"], sample="earlier")
    breadth_p = _find(facts["improvement_breadth"], sample="post_gfc")
    bm_e = _find(facts["size_bm_summary"], sample="earlier")
    bm_p = _find(facts["size_bm_summary"], sample="post_gfc")
    hml_e = _find(facts["hml_summary"], sample="earlier")
    hml_p = _find(facts["hml_summary"], sample="post_gfc")

    family_rows = []
    family_frame = pd.read_csv(facts_path.parent / "cross_family_fit.csv")
    for _, row in family_frame.iterrows():
        family_rows.append([row.family_label, "Earlier" if row["sample"] == "earlier" else "Post-GFC",
            f"{row.CAPM_R2:.3f}", f"{row.FF3_R2:.3f}", f"{row.FF5_R2:.3f}",
            f"{row.FF3_minus_CAPM_R2:+.3f}", f"{row.FF5_minus_CAPM_R2:+.3f}",
            f"{row.CAPM_MAE_pct_month:.3f}", f"{row.FF5_MAE_pct_month:.3f}"])

    bm_rows = []
    for row in [bm_e, bm_p]:
        bm_rows.append(["Earlier" if row["sample"] == "earlier" else "Post-GFC",
            f"{row['CAPM_R2']:.3f}", f"{row['FF3_R2']:.3f}", f"{row['FF5_R2']:.3f}",
            f"{row['CAPM_MAE_pct_month']:.3f}%", f"{row['FF5_MAE_pct_month']:.3f}%",
            f"{row['CAPM_max_abs_error_pct_month']:.3f}%", f"{row['FF5_max_abs_error_pct_month']:.3f}%"])

    hml_rows = []
    for row in facts["hml_diagnostics"]:
        hml_rows.append([row["family_label"], "Earlier" if row["sample"] == "earlier" else "Post-GFC",
            f"{row['lambda_HML_pct_month']:.3f}%", f"{row['HML_t_stat']:.2f}", f"{row['HML_p_value']:.3f}",
            f"{row['delta_R2']:+.3f}"])

    factor_rows = [[row["factor"], "Earlier" if row["sample"] == "earlier" else "Post-GFC",
        f"{row['mean_pct_month']:.3f}%", f"{row['t_stat']:.2f}"] for row in facts["historical_factor_premia"]]
    lambda_rows = [[row["universe"].replace("combined_univariate", "Combined univariate").replace("industries_49", "49 industries"),
        "Earlier" if row["sample"] == "earlier" else "Post-GFC", row["factor"],
        f"{row['mean_lambda_pct_month']:.3f}%", f"{row['std_lambda_pct_month']:.3f}%",
        f"{row['share_positive']:.1%}", f"{row['min_lambda_pct_month']:.2f}% ({row['largest_negative_month']})",
        f"{row['max_lambda_pct_month']:.2f}% ({row['largest_positive_month']})"] for row in facts["lambda_diagnostics"]]
    alpha_rows = [["Earlier" if row["sample"] == "earlier" else "Post-GFC", row["model"],
        f"{row['mean_abs_alpha_pct_month']:.3f}%", f"{row['max_abs_alpha_pct_month']:.3f}%",
        f"{row['mean_abs_alpha_t']:.2f}", f"{int(row['significant_alpha_count'])}/25"] for row in facts["alpha_summary"]]
    grs_rows = [["Earlier" if row["sample"] == "earlier" else "Post-GFC", row["model"],
        f"{row['grs_F']:.3f}", str(int(row["df1"])), str(int(row["df2"])), f"{row['p_value']:.4g}",
        "Reject" if row["reject_5pct"] else "Do not reject"] for row in facts["grs"]]

    q4_early = {factor: _find(facts["two_pass_lambda_summary"], sample="earlier", model="FF5", coefficient=factor)
                for factor in ["MKT", "SMB", "HML", "RMW", "CMA"]}
    q4_post = {factor: _find(facts["two_pass_lambda_summary"], sample="post_gfc", model="FF5", coefficient=factor)
               for factor in ["MKT", "SMB", "HML", "RMW", "CMA"]}

    lines = [
        f"# {facts['title']}", "",
        "> **Status.** This is an interim analytical report based on the post-audit result set. It is not a frozen canonical-production deliverable. All returns, alphas, and lambdas shown in prose and tables are monthly percentage points; underlying CSV files remain in decimal-return units unless their column name explicitly ends in `_pct_month`.", "",
        "## 1. Executive Summary", "",
        f"- **CAPM provides little long-run cross-sectional explanation for most 5×5 families.** Its mean cross-sectional R² is {fit_e['CAPM_mean_R2']:.3f} in July 1963–December 2010 and {fit_p['CAPM_mean_R2']:.3f} after 2010. For Size × Book-to-Market specifically, R² is only {bm_e['CAPM_R2']:.3f} earlier and {bm_p['CAPM_R2']:.3f} post-GFC; the latter is effectively zero despite economically large corner-portfolio errors.", "",
        f"- **FF3 and especially FF5 improve fit broadly, not just in a few families.** Both models raise R² relative to CAPM in all {breadth_e['FF5_improves_R2_families']} families in each sample. Mean R² rises from {fit_e['CAPM_mean_R2']:.3f} to {fit_e['FF3_mean_R2']:.3f} and {fit_e['FF5_mean_R2']:.3f} earlier, and from {fit_p['CAPM_mean_R2']:.3f} to {fit_p['FF3_mean_R2']:.3f} and {fit_p['FF5_mean_R2']:.3f} post-GFC. Mean absolute pricing error falls from {fit_e['CAPM_mean_MAE_pct']:.3f}% to {fit_e['FF5_mean_MAE_pct']:.3f}% per month earlier, but only from {fit_p['CAPM_mean_MAE_pct']:.3f}% to {fit_p['FF5_mean_MAE_pct']:.3f}% post-GFC.", "",
        f"- **The incremental HML evidence inside FF5 is strongly test-asset and period dependent.** Earlier, HML is positive in {hml_e['positive_HML_families']}/11 families and conventionally significant in {hml_e['significant_HML_families']}/11; its median incremental R² is {hml_e['median_delta_R2']:.3f}. Post-GFC it is positive in only {hml_p['positive_HML_families']}/11 and significant in {hml_p['significant_HML_families']}/11, although some families still obtain substantial incremental fit. That pattern does not support a universal redundancy claim.", "",
        "- **Fama–MacBeth prices are much less precise than the full-sample two-pass fits might suggest.** In specification 8, the earlier combined-univariate RMW price is 0.181% per month (FM t = 2.01), while the earlier industry HML price is 0.238% (t = 1.98). None of the five post-GFC factor prices has |t| near 1.96 in either universe. The result depends on the cross-sectional beta variation supplied by the test assets.", "",
        "- **Estimated monthly factor prices are extremely noisy and frequently change sign.** Specification-8 MKT lambda standard deviations range from 4.57% to 5.44% per month across the four universe/sample panels, versus means between 0.002% and 0.426%. Positive shares are generally close to one half. Extreme months are reported without assigning causal stories.", "",
        "- **The selected time-series universe is Size × Momentum.** In the earlier sample, CAPM leaves a pronounced low-to-high momentum alpha pattern, and GRS rejects every model at p < 1.4×10⁻¹⁰. Post-GFC evidence is borderline and model dependent: CAPM p = 0.0637, FF3 p = 0.0489, and FF5 p = 0.0565.", "",
        "- **The three frameworks answer different questions.** FF5 can deliver high cross-sectional R² while still failing the earlier GRS joint-alpha restriction, and volatile monthly lambdas can make FM average prices imprecise even where full-period beta sorts fit average returns well.", "",
        "*Sources: [cross-family fit](../results/tables/interim_report/cross_family_fit.csv), [FM summary](../results/tables/interim_report/fama_macbeth_summary.csv), [lambda diagnostics](../results/tables/interim_report/lambda_time_variation.csv), and [GRS results](../results/tables/interim_report/grs_results.csv).*", "",
        "## 2. Data, Models, and Samples", "",
        "The test assets are eleven value-weighted 25-portfolio Size × Characteristic families, a combined set of 80 univariate characteristic portfolios, and 49 value-weighted industries. CAPM uses MKT; FF3 uses MKT, SMB, and HML; FF5 adds RMW and CMA. MKT is already the market excess return. Every asset return is converted from percent to decimal once and then reduced by RF once in the processed-data layer.", "",
        "The headline earlier sample is July 1963–December 2010 (570 months); the post-GFC sample is January 2011–August 2026 (188 months), the audited latest common endpoint. FM betas require 36 complete months, so the earlier second-stage return sample is July 1966–December 2010 (534 months). The post-GFC FM sample begins in January 2011 because the December 2010 beta legitimately uses January 2008–December 2010 history.", "",
        "## 3. Two-Pass Cross-Sectional Asset-Pricing Evidence", "",
        "### 3.1 Representative Size × Book-to-Market comparison", "",
        "![Four-panel realized-versus-predicted comparison for Size by Book-to-Market](../results/figures/interim_report/size_bm_pricing_four_panel.png)", "",
        "**Figure 1.** Realized and predicted mean monthly excess returns for the 25 Size × Book-to-Market portfolios. Labels identify the three largest absolute pricing errors in each panel. The dashed line is the 45-degree benchmark. Source data: [pricing errors](../results/two_pass/pricing_errors.csv).", "",
        "Earlier, CAPM R² is 0.078, mean absolute pricing error is 0.187% per month, and the largest error is 0.398%. The model underpredicts Small/High B/M by 0.398% and Size-2/High B/M by 0.338%, while overpredicting Big/Low B/M by 0.333%. The signs therefore trace a value-like spread, with meaningful errors at both small-value and big-growth corners.", "",
        "FF5 moves the earlier points substantially toward the diagonal: R² reaches 0.811 and mean absolute error falls to 0.080%. The largest residuals remain economically structured—Size-4/Low B/M is underpredicted by 0.238% and Small/Low B/M is overpredicted by 0.232%—so high fit is not the same as zero pricing error.", "",
        "Post-GFC CAPM R² falls to 0.008. Big/High B/M is underpredicted by 0.453%, Small/Low B/M is overpredicted by 0.339%, and Big/Low B/M is underpredicted by 0.276%. FF5 raises R² to 0.336 and lowers the maximum absolute error to 0.321%, but its mean absolute error (0.091%) is only modestly below CAPM (0.105%). The post-GFC cloud is therefore better organized by FF5 without becoming tightly aligned with the diagonal.", "",
        "**Table 1. Size × B/M model comparison.** Errors are percentage points per month.", "",
        *_table(["Sample", "CAPM R²", "FF3 R²", "FF5 R²", "CAPM MAE", "FF5 MAE", "CAPM max \\|e\\|", "FF5 max \\|e\\|"], bm_rows), "",
        "### 3.2 Evidence across all eleven families", "",
        "**Table 2. Cross-sectional fit and pricing errors across 5×5 families.** MAE is mean absolute pricing error in percentage points per month.", "",
        *_table(["Family", "Sample", "CAPM R²", "FF3 R²", "FF5 R²", "ΔR² FF3", "ΔR² FF5", "CAPM MAE", "FF5 MAE"], family_rows), "",
        "The improvement is broad: FF5 raises R² for every family in both samples. Earlier gains are especially large for Operating Profitability (+0.879), Market Beta (+0.840), Momentum (+0.798), and Long-Term Reversal (+0.775). Post-GFC gains are smaller and more heterogeneous: only +0.036 for Momentum, versus +0.582 for Variance. Thus the factors' incremental cross-sectional content is much weaker for post-GFC momentum portfolios but remains substantial for variance-related sorts.", "",
        "The largest CAPM error across all earlier families is Small/High Momentum at +0.796% per month; Small/High Short-Term Reversal, Small/High Variance, and Small/High Residual Variance have errors from −0.671% to −0.697%. Post-GFC the largest is Small/High Variance at −0.797%, followed by Big/portfolio-3 Net Share Issues at +0.660% and Small/High Residual Variance at −0.642%. CAPM failures cluster in extreme characteristic cells, often among small firms, but are not exclusively small-stock phenomena.", "",
        "### 3.3 HML inside FF5", "",
        "The reduced cross section uses MKT, SMB, RMW, and CMA betas taken from the full FF5 first pass; the full cross section adds HML. Earlier Size × B/M is the clearest positive case: HML is 0.380% per month (t = 6.26) and adds 0.389 to R². Earlier Momentum is the clearest negative case: −0.872% (t = −4.58), adding 0.135. Market Beta is also positive and significant at 0.625% (t = 2.26). These opposite signs show that the HML price depends on which beta cross section identifies it.", "",
        "Post-GFC, only Long-Term Reversal is conventionally significant: −0.254% (t = −2.13), with ΔR² = 0.140. Size × B/M itself has essentially no incremental HML evidence in this period—0.006% (t = 0.08), ΔR² = 0.0002—while Momentum and Short-Term Reversal obtain positive but imprecise HML prices. HML is therefore neither uniformly indispensable nor uniformly redundant.", "",
        "The full family-level diagnostic appears in Appendix Table A1 and [the machine-readable HML table](../results/tables/interim_report/hml_diagnostics.csv).", "",
        "## 4. Fama–MacBeth Evidence", "",
        "### 4.1 Eight specifications", "",
        "Each cell below is the mean monthly lambda in percentage points followed by the conventional FM t-statistic in parentheses. HAC estimates use six lags and are available in the linked structured table.", "",
        "**Table 3A. Combined univariate portfolios — Earlier.**", "", *_fm_panel(facts, "combined_univariate", "earlier"), "",
        "**Table 3B. Combined univariate portfolios — Post-GFC.**", "", *_fm_panel(facts, "combined_univariate", "post_gfc"), "",
        "**Table 4A. 49 industries — Earlier.**", "", *_fm_panel(facts, "industries_49", "earlier"), "",
        "**Table 4B. 49 industries — Post-GFC.**", "", *_fm_panel(facts, "industries_49", "post_gfc"), "",
        "Earlier combined-univariate results attach the most stable positive price to RMW: it is 0.218% (t = 2.18) in specification 5, 0.161% (t = 2.11) in specification 7, and 0.181% (t = 2.01) in specification 8. HML is positive but less precise in the full specification (0.167%, t = 1.41). For industries, HML is more prominent: 0.247% (t = 2.08) in FF3/specification 2 and 0.238% (t = 1.98) in specification 8. The full-specification MKT and SMB prices are near zero for industries.", "",
        "Post-GFC factor-price precision deteriorates in both universes. In combined univariate portfolios, specification-8 MKT is 0.426% (t = 1.28), while SMB, HML, and CMA are negative but insignificant. In industries, HML remains positive at 0.238% but has t = 0.96; the other four prices are also imprecise. Intercepts, however, are often positive and statistically detectable, which cautions against interpreting weak factor prices as successful conditional pricing.", "",
        "### 4.2 Historical premia and economic signs", "",
        "**Table 5. Historical factor means over the headline samples.**", "", *_table(["Factor", "Sample", "Mean return", "t-stat"], factor_rows), "",
        "In the earlier period all five historical factor means are positive. Specification-8 FM signs broadly agree for SMB, HML, RMW, and CMA in the combined-univariate cross section, but MKT is slightly negative; industries produce positive HML/RMW/CMA but near-zero MKT and negative SMB. Post-GFC historical SMB, HML, and CMA means are negative. The combined-univariate FM prices share those signs, whereas industry HML is positive and industry SMB/CMA are approximately zero. These discrepancies are economically plausible because FM lambdas price cross-sectional beta variation and need not reproduce the factor portfolios' time-series means.", "",
        "### 4.3 Monthly lambda variation", "",
        "![Four-panel raw monthly specification-8 lambda series](../results/figures/interim_report/fm_spec8_lambdas_four_panel.png)", "",
        "**Figure 2.** Raw monthly specification-8 factor prices for both universes and samples. No smoothing is applied. Source: [monthly lambdas](../results/fama_macbeth/monthly_lambdas/all.csv).", "",
        "MKT is the most volatile factor price in every panel: its standard deviation is 4.71% earlier and 4.57% post-GFC for combined univariate portfolios, and 4.84% and 5.44% for industries. Its sign is positive in only 47.2%, 53.7%, 48.5%, and 48.4% of months, respectively. The largest positive MKT estimates are 22.06% (April 2009) and 21.48% (April 2020) for combined portfolios, and 33.15% (April 2009) and 17.55% (August 2020) for industries.", "",
        "HML also changes sign frequently. For combined portfolios its positive share drops from 50.9% earlier to 43.1% post-GFC; the post-GFC range is −17.48% in March 2020 to +10.54% in January 2022. Industry HML remains positive in about half the months. RMW and CMA are less volatile than MKT, but their standard deviations still exceed 1.95% per month in every panel—far larger than their average prices.", "",
        "## 5. Time-Series Alpha and GRS Evidence", "",
        "The audited GRS family is **Size × Momentum**. Rows are Size buckets and columns run from Low to High Momentum.", "",
        "![CAPM alpha t-stat grid, earlier sample](../results/figures/time_series/size_momentum__earlier__CAPM__alpha_t.png)", "",
        "**Figure 3A.** CAPM alpha t-statistics, July 1963–December 2010.", "",
        "![CAPM alpha t-stat grid, post-GFC sample](../results/figures/time_series/size_momentum__post_gfc__CAPM__alpha_t.png)", "",
        "**Figure 3B.** CAPM alpha t-statistics, January 2011–August 2026.", "",
        "Earlier CAPM alphas display a strong monotonic momentum pattern within the smaller size rows: Low Momentum t-statistics are negative, while columns 4 and 5 are broadly positive. Small/High Momentum has alpha 0.822% per month (t = 4.73); the most negative CAPM t-stat is Size-2/Low Momentum, −0.563% (t = −2.90). Seventeen of 25 CAPM alphas have individual p-values below 5%.", "",
        "After 2010 the grid is less monotonic and generally less individually significant. The strongest negative is Size-3/Low Momentum at −1.076% (t = −3.41); the strongest positive t-stat belongs to Big/portfolio-3 at 0.225% (t = 2.18). Five CAPM alphas are individually significant.", "",
        "Adding factors reduces mean absolute alpha from 0.346% under CAPM to 0.331% under FF3 and 0.294% under FF5 earlier, but it does not remove the small-stock momentum spread: under FF5, Small/High Momentum is +0.645% (t = 6.38) and Small/Low Momentum is −0.751% (t = −4.55). Post-GFC, mean absolute alpha falls from 0.314% to 0.224% under FF3 and 0.231% under FF5, while Size-3/Low Momentum remains near −0.74% with t around −3.0.", "",
        "**Table 6. Portfolio-alpha summary.**", "", *_table(["Sample", "Model", "Mean \\|alpha\\|", "Max \\|alpha\\|", "Mean \\|t\\|", "p < 5%"], alpha_rows), "",
        "**Table 7. GRS joint-alpha tests.**", "", *_table(["Sample", "Model", "GRS F", "df1", "df2", "p-value", "5% decision"], grs_rows), "",
        "The earlier individual and joint evidence agree that all three models leave systematic momentum-related returns. Post-GFC they give a more nuanced picture: several individual alphas remain significant, yet the joint tests are near the 5% boundary. FF3 rejects at 4.89%, while CAPM and FF5 do not at 6.37% and 5.65%. Residual covariance and the full alpha vector, not a count of individual t-tests, determine GRS.", "",
        "## 6. Integrated Interpretation Across the Three Testing Frameworks", "",
        *_table(["Framework", "Main object", "Economic question"], [
            ["Two-pass", "Lambda from average-return cross section", "Are long-run average returns related to full-sample factor betas?"],
            ["Fama–MacBeth", "Monthly predictive lambda_t", "Do exposures estimated through t predict returns at t+1?"],
            ["Time-series / GRS", "Portfolio alpha_i", "Does the model leave systematic unexplained returns?"]]), "",
        "The empirical results are not contradictory. FF5's mean two-pass R² of 0.808 earlier says its beta pattern spans much of the variation in average returns across each 25-asset family. It does not imply that all time-series intercepts are zero: on Size × Momentum, earlier GRS still rejects FF5 decisively. Similarly, the weak average FM t-statistics reflect large month-to-month lambda variation and beta-estimation noise; they do not undo the descriptive full-sample cross-sectional fit. Finally, adding a factor can improve time-series or cross-sectional fit without producing a precisely estimated price for that factor in every asset universe.", "",
        "## 7. Answers to Analysis and Interpretation Questions", "",
        "### 1. Does the CAPM price the cross section of the 5×5 portfolios? Where are its largest systematic pricing errors?", "",
        f"Generally, no. CAPM mean R² across the eleven families is {fit_e['CAPM_mean_R2']:.3f} earlier and {fit_p['CAPM_mean_R2']:.3f} post-GFC. Size × B/M R² is {bm_e['CAPM_R2']:.3f} and {bm_p['CAPM_R2']:.3f}; across families, CAPM R² ranges from 0.001 for earlier Net Share Issues to 0.324 for earlier Short-Term Reversal, and from 0.007 for post-GFC Net Share Issues to 0.514 for post-GFC Momentum.", "",
        "The largest earlier error is Small/High Momentum (+0.796% per month). Extreme Small/High Short-Term Reversal, Variance, and Residual Variance portfolios have errors near −0.67% to −0.70%. Post-GFC, Small/High Variance is −0.797%, Big/portfolio-3 Net Share Issues is +0.660%, and Small/High Residual Variance is −0.642%. In Size × B/M, errors appear at both value and growth corners rather than in one size bucket alone.", "",
        "### 2. How much do FF3 and FF5 improve cross-sectional pricing, and is improvement consistent?", "",
        f"Earlier, mean R² rises from {fit_e['CAPM_mean_R2']:.3f} under CAPM to {fit_e['FF3_mean_R2']:.3f} under FF3 and {fit_e['FF5_mean_R2']:.3f} under FF5; mean absolute error falls from {fit_e['CAPM_mean_MAE_pct']:.3f}% to {fit_e['FF3_mean_MAE_pct']:.3f}% and {fit_e['FF5_mean_MAE_pct']:.3f}%. Post-GFC, mean R² rises from {fit_p['CAPM_mean_R2']:.3f} to {fit_p['FF3_mean_R2']:.3f} and {fit_p['FF5_mean_R2']:.3f}, while mean absolute errors fall more modestly from {fit_p['CAPM_mean_MAE_pct']:.3f}% to {fit_p['FF3_mean_MAE_pct']:.3f}% and {fit_p['FF5_mean_MAE_pct']:.3f}%.", "",
        "R² improves in all eleven families in both samples, but magnitudes differ sharply. Earlier FF5 gains range from +0.541 for Short-Term Reversal to +0.879 for Profitability; post-GFC gains range from only +0.036 for Momentum to +0.582 for Variance. The improvement is broad but not uniform, and post-GFC error reductions are much less dramatic than R² comparisons alone suggest.", "",
        "### 3. Does HML retain an independent price in FF5?", "",
        f"Earlier, the median family HML price is {hml_e['median_HML_pct']:.3f}% per month and the median ΔR² is {hml_e['median_delta_R2']:.3f}; 3 of 11 prices are significant at 5%. Size × B/M is strongly positive, Momentum strongly negative, and Market Beta positive. This is evidence that HML can add information, but its price is not invariant to the test assets.", "",
        f"Post-GFC, the median price is {hml_p['median_HML_pct']:.3f}%, only one family is significant, and signs are positive in 4 of 11 families. Long-Term Reversal has a significant negative HML price and the largest ΔR², while Size × B/M has virtually zero incremental fit. The appropriate conclusion is sample- and asset-dependent identification—not blanket redundancy or universal pricing.", "",
        "### 4. How do factor prices differ between 1963–2010 and the post-GFC period?", "",
        f"In the two-pass FF5 cross sections, median prices across families shift from MKT {q4_early['MKT']['median_pct_month']:.3f}%, SMB {q4_early['SMB']['median_pct_month']:.3f}%, HML {q4_early['HML']['median_pct_month']:.3f}%, RMW {q4_early['RMW']['median_pct_month']:.3f}%, and CMA {q4_early['CMA']['median_pct_month']:.3f}% earlier to MKT {q4_post['MKT']['median_pct_month']:.3f}%, SMB {q4_post['SMB']['median_pct_month']:.3f}%, HML {q4_post['HML']['median_pct_month']:.3f}%, RMW {q4_post['RMW']['median_pct_month']:.3f}%, and CMA {q4_post['CMA']['median_pct_month']:.3f}% post-GFC. SMB and HML notably change from positive to negative medians.", "",
        "In predictive FM specification 8, combined-univariate MKT moves from −0.061% to +0.426%, while SMB/HML/CMA move from positive to negative; RMW remains positive but shrinks. Industries differ: HML remains about +0.238% in both samples, while MKT rises from essentially zero to +0.254%. None of the post-GFC factor prices is precisely estimated.", "",
        "### 5. Are FM factor-price signs economically sensible relative to historical premia?", "",
        "Earlier historical means are positive for all five factors. Combined-univariate specification-8 signs match for SMB, HML, RMW, and CMA, but not MKT; industries match for HML, RMW, and CMA, with near-zero MKT and negative SMB. Post-GFC historical SMB, HML, and CMA premia are negative, matching combined-univariate FM signs. Industry HML is instead positive, and industry SMB/CMA are nearly zero.", "",
        "The partial sign agreement is economically sensible but not mechanical validation. Factor returns are payoffs to particular long-short portfolios; FM lambdas are prices inferred from the beta dispersion of a chosen test-asset cross section. Weak beta dispersion, sampling noise, and model misspecification can separate the two.", "",
        "### 6. Are FM conclusions sensitive to characteristic portfolios versus industries?", "",
        "Yes. Earlier, combined portfolios emphasize RMW (0.181%, t = 2.01 in specification 8), whereas industries emphasize HML (0.238%, t = 1.98). Earlier industry MKT and SMB prices are virtually zero, while combined portfolios provide somewhat more positive SMB/RMW structure. Post-GFC, combined HML is negative (−0.148%, t = −0.58), but industry HML is positive (+0.238%, t = 0.96).", "",
        "Characteristic sorts are constructed to spread firm attributes and often generate stronger dispersion in corresponding factor betas and expected returns. Industries instead vary by economic activity and may span factor exposures differently. The coefficients therefore answer asset-universe-specific cross-sectional questions; neither universe alone supplies a universal price vector.", "",
        "### 7. How volatile are specification-8 monthly factor prices?", "",
        "Very volatile. MKT lambda standard deviations are 4.57%–5.44% per month, with signs close to evenly split. HML standard deviations are 2.74%–3.51%; RMW and CMA are lower but still about 1.95%–2.43%. These dispersions dwarf the corresponding mean lambdas.", "",
        "Notable computed extremes include combined-univariate MKT +22.06% in April 2009 and −21.25% in November 2000; post-GFC combined HML reaches −17.48% in March 2020 and +10.54% in January 2022. Industry MKT reaches +33.15% in April 2009 and post-GFC ranges from −17.04% in September 2011 to +17.55% in August 2020. The report does not assign causal event explanations to these dates.", "",
        "### 8. What are the limitations of a fixed 36-month rolling-beta window?", "",
        "Thirty-six observations produce noisy multivariate beta estimates, especially for FF5, creating an errors-in-variables problem in the second-stage cross sections. A longer window would reduce variance but increase bias when exposures change; a shorter window would adapt faster but amplify estimation noise. The method assumes exposures are locally stable inside each window and cannot react instantly to structural breaks or a single abrupt regime change.", "",
        "Adjacent windows share 35 of 36 observations, making estimated betas highly serially dependent. Extreme returns can influence many successive windows. Requiring complete observations can also change the available cross section when data are missing. The audited t−35 through t → t+1 alignment prevents look-ahead bias, but it does not remove beta noise, overlap-induced dependence, sensitivity to outliers, or attenuation and instability in estimated factor prices.", "",
        "### 9. Do individual alpha tests and GRS tell the same story?", "",
        "Earlier they broadly agree: many momentum-portfolio alphas are individually significant—17 under CAPM, 17 under FF3, and 19 under FF5—and GRS rejects all three models with p-values below 1.4×10⁻¹⁰. FF5 lowers mean absolute alpha but leaves an especially strong Small Low-to-High Momentum contrast, so improved fit does not satisfy the zero-alpha restriction.", "",
        "Post-GFC the impressions differ. Individual significant-alpha counts are 5, 7, and 7, yet GRS p-values are 0.0637, 0.0489, and 0.0565 for CAPM, FF3, and FF5. GRS jointly weights the full alpha vector by residual covariance; several modest correlated alphas may reject, while one large t-statistic need not. The borderline post-GFC decisions should not be presented as a stable ranking of models.", "",
        "## 8. Methodological Limitations", "",
        "Beyond rolling-beta limitations, the two-pass estimates treat first-pass betas as regressors without a Shanken-style errors-in-variables correction. The eleven families are related rather than independent experiments, so family-level significance counts do not correct for multiple testing. Cross-sectional R² can rise mechanically with additional regressors and does not establish zero alphas. FM results depend on test-asset beta dispersion and use conventional time-series inference as the primary assignment result; six-lag HAC estimates are a robustness diagnostic, not a cure for all dependence. GRS assumes stable linear factor structure, invertible covariance matrices, and the selected 25-asset universe. Finally, Kenneth French histories can be revised, so the source hashes and August 2026 endpoint are part of the result definition.", "",
        "## 9. Concluding Takeaways", "",
        "CAPM does not organize the eleven 5×5 average-return cross sections well, and its largest errors concentrate in economically extreme characteristic cells. FF3 and FF5 improve cross-sectional fit across every family, with FF5 strongest in the earlier sample, but post-GFC gains are smaller and residual error patterns remain.", "",
        "HML's incremental role is conditional: it is powerful for some earlier cross sections, irrelevant for post-GFC Size × B/M, and negative for other families. FM evidence is likewise universe dependent and generally imprecise because monthly factor prices are highly volatile. Time-series evidence for Size × Momentum remains the most demanding: all three models fail the earlier joint-alpha test, while post-GFC GRS results sit near the conventional threshold. Taken together, the models describe important dimensions of average returns without delivering a single, stable, universally validated price system.", "",
        "## Appendix: Supporting Tables and Figures", "",
        "### Appendix Table A1. HML incremental diagnostic by family", "",
        *_table(["Family", "Sample", "HML price", "t", "p", "ΔR²"], hml_rows), "",
        "### Appendix Table A2. Specification-8 lambda time-variation diagnostics", "",
        *_table(["Universe", "Sample", "Factor", "Mean", "Std. dev.", "Share +", "Minimum (month)", "Maximum (month)"], lambda_rows), "",
        "### Artifact references", "",
        "- Additional two-pass plots for all eleven families: [`results/figures/two_pass/`](../results/figures/two_pass/)",
        "- Individual specification-8 lambda plots: [`results/figures/fama_macbeth/`](../results/figures/fama_macbeth/)",
        "- Alpha and alpha-t grids for CAPM, FF3, and FF5: [`results/figures/time_series/`](../results/figures/time_series/)",
        "- Full report-ready structured tables: [`results/tables/interim_report/`](../results/tables/interim_report/)",
        "- Audited result inventory and source hashes: [`production_manifest.json`](../production_manifest.json)", "",
        "The selected GRS family is `size_momentum`. Headline samples are July 1963–December 2010 and January 2011–August 2026; effective FM return samples are July 1966–December 2010 and January 2011–August 2026.", "",
    ]
    if canonical:
        lines[2] = (
            "> **Status.** This is the frozen canonical-production report. Every empirical "
            "claim is derived from the fresh canonical run. All returns, alphas, and lambdas "
            "shown in prose and tables are monthly percentage points; underlying CSV files "
            "remain in decimal-return units unless their column name explicitly ends in "
            "`_pct_month`."
        )
        canonical_text = "\n".join(lines)
        canonical_text = canonical_text.replace(
            "../results/tables/interim_report/", "../tables/"
        ).replace(
            "../results/figures/interim_report/", "../figures/"
        ).replace(
            "[`results/tables/interim_report/`](../tables/)",
            "[`tables/`](../tables/)",
        )
        lines = canonical_text.splitlines()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


if __name__ == "__main__":
    build_report()
