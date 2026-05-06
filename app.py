"""
Physics-Informed Snowmelt Emulator — Interactive Dashboard
Western US CMIP6 Projections 2024–2100
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.path import Path as MplPath
import streamlit as st
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ── Page config ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Snowmelt Projections — Western US",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ──────────────────────────────────────────────────────────
MODELS = ["mri_esm2_0", "gfdl_esm4", "canesm5"]
MODEL_LABELS = {
    "mri_esm2_0": "MRI-ESM2-0 (medium sensitivity)",
    "gfdl_esm4":  "GFDL-ESM4 (medium-high sensitivity)",
    "canesm5":    "CanESM5 (high sensitivity)",
    "ensemble":   "3-Model Ensemble",
}
SCENARIOS = ["ssp245", "ssp585"]
SCENARIO_LABELS = {
    "ssp245": "SSP2-4.5 — Moderate emissions",
    "ssp585": "SSP5-8.5 — High emissions",
}
SC_COL = {"ssp245": "#1e40af", "ssp585": "#dc2626"}

BASINS = {
    "Colorado River": {
        "color": "#dc2626",
        "desc":  "40M people across 7 states",
        "poly":  [(-115.5,42.0),(-114.0,42.0),(-111.5,42.0),
                  (-107.0,41.0),(-105.5,40.0),(-104.5,37.0),
                  (-114.5,32.0),(-117.0,32.5),(-116.0,35.0),
                  (-115.5,38.0),(-115.5,42.0)],
    },
    "Columbia River": {
        "color": "#1e40af",
        "desc":  "Largest Pacific-draining basin",
        "poly":  [(-124.0,49.5),(-110.0,49.5),(-110.0,46.0),
                  (-113.0,44.0),(-116.0,43.5),(-120.0,43.5),
                  (-124.0,46.0),(-124.0,49.5)],
    },
    "Sacramento-San Joaquin": {
        "color": "#16a34a",
        "desc":  "California's primary water supply",
        "poly":  [(-122.5,42.0),(-119.5,42.0),(-119.0,39.0),
                  (-120.5,37.5),(-122.0,37.5),(-122.5,39.0),
                  (-122.5,42.0)],
    },
    "Missouri Headwaters": {
        "color": "#d97706",
        "desc":  "Northern Rockies snowpack",
        "poly":  [(-113.0,49.5),(-104.0,49.5),(-104.0,44.5),
                  (-108.0,43.5),(-111.0,44.0),(-113.0,46.0),
                  (-113.0,49.5)],
    },
    "Rio Grande Headwaters": {
        "color": "#7c3aed",
        "desc":  "US-Mexico border water",
        "poly":  [(-108.0,38.5),(-104.5,38.5),(-104.0,35.0),
                  (-106.5,31.5),(-109.0,31.5),(-109.0,35.0),
                  (-108.0,38.5)],
    },
}

DECADES = ["2030s", "2050s", "2070s", "2090s"]

# ── Load data ──────────────────────────────────────────────────────────
@st.cache_data
def load_results():
    path = Path("data/pinn_results/all_results.npy")
    if not path.exists():
        return None
    return np.load(path, allow_pickle=True).item()

@st.cache_data
def get_era5_grid():
    """Return lat/lon arrays for ERA5 grid."""
    lats = np.linspace(50.0, 31.0, 191)
    lons = np.linspace(-125.0, -102.0, 231)
    return lats, lons

@st.cache_data
def build_basin_masks():
    lats, lons = get_era5_grid()
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    pts = np.column_stack([lon_grid.ravel(), lat_grid.ravel()])
    masks = {}
    for name, info in BASINS.items():
        masks[name] = MplPath(info["poly"]).contains_points(pts
                      ).reshape(lon_grid.shape)
    return masks

@st.cache_data
def compute_annual_ts(scenario, model_name):
    results = load_results()
    if results is None:
        return None, None
    res  = results[model_name][scenario]
    ts   = pd.Series(res["melt_mean"], index=res["times"])
    ann  = ts.resample("YE").mean()
    return ann.index.year, ann.values

@st.cache_data
def compute_ensemble(scenario):
    results = load_results()
    if results is None:
        return None, None, None, None
    vals = []
    for m in MODELS:
        yrs, v = compute_annual_ts(scenario, m)
        vals.append(v)
    arr = np.array(vals)
    return yrs, arr.mean(0), arr.min(0), arr.max(0)

@st.cache_data
def get_basin_pcts(basin_name):
    results = load_results()
    if results is None:
        return {}
    masks   = build_basin_masks()
    mask    = masks[basin_name]
    pcts    = {}
    for scenario in SCENARIOS:
        model_pcts = []
        for m in MODELS:
            res  = results[m][scenario]
            dm   = res["decade_maps"]
            d30  = dm["2030s"]; d90 = dm["2090s"]
            s30  = np.nanmean(d30[mask]) / max(
                   np.nanmean(d30[np.isfinite(d30)]), 1e-6)
            s90  = np.nanmean(d90[mask]) / max(
                   np.nanmean(d90[np.isfinite(d90)]), 1e-6)
            ts   = pd.Series(res["melt_mean"], index=res["times"])
            ann  = ts.resample("YE").mean()
            yrs  = ann.index.year
            base = float(ann.values[:3].mean()) * s30
            late = float(ann.values[yrs >= 2090].mean()) * s90
            model_pcts.append(100*(late-base)/base if base > 0 else 0)
        pcts[scenario] = {
            "mean": float(np.mean(model_pcts)),
            "min":  float(np.min(model_pcts)),
            "max":  float(np.max(model_pcts)),
        }
    return pcts

# ── Sidebar ────────────────────────────────────────────────────────────
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/"
        "1/1e/Snowflake_macro_photography_1.jpg/"
        "320px-Snowflake_macro_photography_1.jpg",
        use_container_width=True
    )
    st.title("❄️ Snowmelt\nProjections")
    st.caption("Western US | 2024–2100")
    st.divider()

    page = st.radio(
        "Navigate",
        ["📈 Projections", "🗺️ Spatial Maps",
         "🌊 River Basins", "ℹ️ About"],
        label_visibility="collapsed"
    )
    st.divider()

    st.markdown("**Controls**")
    selected_scenario = st.selectbox(
        "Emissions scenario",
        SCENARIOS,
        format_func=lambda x: SCENARIO_LABELS[x]
    )
    selected_model = st.selectbox(
        "CMIP6 model",
        ["ensemble"] + MODELS,
        format_func=lambda x: MODEL_LABELS[x]
    )
    selected_basin = st.selectbox(
        "River basin",
        list(BASINS.keys())
    )
    selected_decade = st.selectbox(
        "Decade (spatial maps)",
        DECADES, index=3
    )

    st.divider()
    st.markdown(
        "**Links**\n\n"
        "[![Phase 1](https://img.shields.io/badge/Phase_1-Colorado-blue)]"
        "(https://github.com/IpshitaPPradhan/snowmelt-pinn) "
        "[![Phase 2](https://img.shields.io/badge/Phase_2-Western_US-green)]"
        "(https://github.com/IpshitaPPradhan/snowmelt-pinn-v2)"
    )

# ── Load data ──────────────────────────────────────────────────────────
results = load_results()
if results is None:
    st.error(
        "⚠️ Data not found. Make sure `data/pinn_results/all_results.npy` "
        "exists in the app directory."
    )
    st.stop()

lats, lons = get_era5_grid()
lon_grid, lat_grid = np.meshgrid(lons, lats)
basin_masks = build_basin_masks()

# ══════════════════════════════════════════════════════════════════════
# PAGE: PROJECTIONS
# ══════════════════════════════════════════════════════════════════════
if page == "📈 Projections":
    st.title("Western US Snowmelt Projections 2024–2100")
    st.caption(
        "Physics-Informed Neural Network (PINN v2) | "
        "ERA5-Land baseline + CMIP6 bias-corrected forcing"
    )

    # ── Metric cards ──
    col1, col2, col3, col4 = st.columns(4)

    # Compute key stats
    yrs245, e245, mn245, mx245 = compute_ensemble("ssp245")
    yrs585, e585, mn585, mx585 = compute_ensemble("ssp585")
    base245  = float(e245[:3].mean())
    end245   = float(e245[-10:].mean())
    end585   = float(e585[-10:].mean())
    pct245   = 100*(end245-base245)/base245
    pct585   = 100*(end585-base245)/base245
    spread   = float(mx585[-10:].mean() - mn585[-10:].mean())

    col1.metric("SSP2-4.5 change by 2090s",
                f"+{pct245:.0f}%", "vs 2024–2026")
    col2.metric("SSP5-8.5 change by 2090s",
                f"+{pct585:.0f}%", "vs 2024–2026",
                delta_color="inverse")
    col3.metric("Emissions gap (2090s)",
                f"{pct585-pct245:.0f}pp",
                "SSP5-8.5 minus SSP2-4.5")
    col4.metric("Model spread (2090s)",
                f"±{spread/2:.2f} mm/day",
                "3-model ensemble range")

    st.divider()

    # ── Time series plot ──
    fig, ax = plt.subplots(figsize=(12, 5))

    for sc in SCENARIOS:
        yrs, ens, mn, mx = compute_ensemble(sc)
        ax.fill_between(yrs, mn, mx, alpha=0.15, color=SC_COL[sc])
        ax.plot(yrs, ens, color=SC_COL[sc], linewidth=2.5,
                label=SCENARIO_LABELS[sc])

        if selected_model != "ensemble":
            m_yrs, m_vals = compute_annual_ts(sc, selected_model)
            ax.plot(m_yrs, m_vals, color=SC_COL[sc],
                    linewidth=1.2, linestyle="--", alpha=0.6,
                    label=f"{MODEL_LABELS[selected_model]} ({sc})")

    ax.axhline(base245, color="gray", linewidth=1,
               linestyle=":", alpha=0.7, label="2024–2026 baseline")
    ax.set_xlabel("Year", fontsize=11)
    ax.set_ylabel("Mean Melt (mm/day)", fontsize=11)
    ax.set_xlim(2024, 2100)
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(True, alpha=0.3)
    ax.set_title(
        f"Western US Ensemble Mean Melt — {MODEL_LABELS[selected_model]}",
        fontsize=12, fontweight="bold"
    )
    st.pyplot(fig, use_container_width=True)
    plt.close()

    # ── Scenario comparison ──
    st.subheader("End-of-century change by model")
    cols = st.columns(len(MODELS))
    for col, m in zip(cols, MODELS):
        m_yrs245, m_v245 = compute_annual_ts("ssp245", m)
        m_yrs585, m_v585 = compute_annual_ts("ssp585", m)
        base  = float(m_v245[:3].mean())
        p245  = 100*(float(m_v245[-10:].mean()) - base) / base
        p585  = 100*(float(m_v585[-10:].mean()) - base) / base
        col.markdown(f"**{MODEL_LABELS[m].split('(')[0].strip()}**")
        col.metric("SSP2-4.5", f"+{p245:.0f}%")
        col.metric("SSP5-8.5", f"+{p585:.0f}%",
                   delta_color="inverse")

# ══════════════════════════════════════════════════════════════════════
# PAGE: SPATIAL MAPS
# ══════════════════════════════════════════════════════════════════════
elif page == "🗺️ Spatial Maps":
    st.title("Spatial Melt Maps")
    st.caption(
        f"Spring (Apr–May) ensemble mean | "
        f"{selected_decade} | {SCENARIO_LABELS[selected_scenario]}"
    )

    # Get decade maps
    if selected_model == "ensemble":
        maps = [results[m][selected_scenario]["decade_maps"][selected_decade]
                for m in MODELS]
        melt_map = np.nanmean(maps, axis=0)
        title_suffix = "Ensemble Mean"
    else:
        melt_map = results[selected_model][selected_scenario
                   ]["decade_maps"][selected_decade]
        title_suffix = MODEL_LABELS[selected_model]

    col_map, col_info = st.columns([2, 1])

    with col_map:
        fig, ax = plt.subplots(figsize=(10, 8))

        vals = melt_map[np.isfinite(melt_map)]
        vmax = float(np.percentile(vals, 95)) if len(vals) > 0 else 1.0

        im = ax.pcolormesh(
            lons, lats, melt_map,
            cmap="YlOrRd", vmin=0, vmax=vmax,
            shading="auto"
        )
        plt.colorbar(im, ax=ax, label="Spring Melt (mm/day)",
                     shrink=0.8)

        # Highlight selected basin
        sel_poly = np.array(BASINS[selected_basin]["poly"])
        sel_col  = BASINS[selected_basin]["color"]
        patch    = plt.Polygon(sel_poly, fill=False,
                               edgecolor=sel_col,
                               linewidth=3, zorder=5)
        ax.add_patch(patch)
        cx = np.mean(sel_poly[:,0])
        cy = np.mean(sel_poly[:,1])
        ax.text(cx, cy, selected_basin,
                ha="center", va="center", fontsize=9,
                fontweight="bold", color=sel_col,
                bbox=dict(boxstyle="round,pad=0.3",
                          facecolor="white", alpha=0.85))

        ax.set_xlim(-125, -102); ax.set_ylim(31, 50)
        ax.set_xlabel("Longitude", fontsize=10)
        ax.set_ylabel("Latitude", fontsize=10)
        ax.set_title(
            f"{selected_decade} Spring Melt | "
            f"{SCENARIO_LABELS[selected_scenario]}\n{title_suffix}",
            fontsize=11, fontweight="bold"
        )
        ax.grid(True, alpha=0.2)
        st.pyplot(fig, use_container_width=True)
        plt.close()

    with col_info:
        st.markdown("### Map Statistics")
        valid = melt_map[np.isfinite(melt_map) & (melt_map > 0.005)]
        st.metric("Domain mean", f"{np.nanmean(melt_map):.4f} mm/day")
        st.metric("Mountain peak", f"{float(np.nanpercentile(valid, 95)):.4f} mm/day"
                  if len(valid) > 0 else "N/A")
        st.metric("Active melt area",
                  f"{(melt_map > 0.02).mean()*100:.1f}%")

        st.divider()
        st.markdown("### Decade comparison")
        st.caption(f"{SCENARIO_LABELS[selected_scenario]}")

        dec_vals = {}
        for dec in DECADES:
            if selected_model == "ensemble":
                dm = np.nanmean(
                    [results[m][selected_scenario]["decade_maps"][dec]
                     for m in MODELS], axis=0)
            else:
                dm = results[selected_model][selected_scenario
                     ]["decade_maps"][dec]
            dec_vals[dec] = float(np.nanmean(dm))

        base_val = dec_vals["2030s"]
        for dec, val in dec_vals.items():
            pct = 100*(val-base_val)/base_val if base_val > 0 else 0
            st.metric(dec, f"{val:.4f} mm/day",
                      f"{pct:+.0f}% vs 2030s" if dec != "2030s" else "baseline")

        st.divider()
        st.markdown("### Selected basin")
        st.markdown(f"**{selected_basin}**")
        st.caption(BASINS[selected_basin]["desc"])

        mask = basin_masks[selected_basin]
        basin_val = float(np.nanmean(melt_map[mask]))
        st.metric(f"{selected_decade} basin mean",
                  f"{basin_val:.4f} mm/day")

    # ── All decades side by side ──
    st.subheader(f"All decades — {SCENARIO_LABELS[selected_scenario]}")
    fig, axes = plt.subplots(1, 4, figsize=(20, 5))

    all_dec_maps = []
    for dec in DECADES:
        if selected_model == "ensemble":
            dm = np.nanmean(
                [results[m][selected_scenario]["decade_maps"][dec]
                 for m in MODELS], axis=0)
        else:
            dm = results[selected_model][selected_scenario
                 ]["decade_maps"][dec]
        all_dec_maps.append(dm)

    vmax_all = float(np.nanpercentile(
        np.concatenate([d[np.isfinite(d)].flatten()
                        for d in all_dec_maps]), 95))

    for i, (dec, dm) in enumerate(zip(DECADES, all_dec_maps)):
        ax = axes[i]
        ax.pcolormesh(lons, lats, dm,
                      cmap="YlOrRd", vmin=0, vmax=vmax_all,
                      shading="auto")
        ax.set_xlim(-125, -102); ax.set_ylim(31, 50)
        ax.set_aspect("equal"); ax.tick_params(labelsize=7)
        ax.set_title(dec, fontsize=11, fontweight="bold")
        ax.set_xlabel("Lon", fontsize=8)
        if i == 0:
            ax.set_ylabel("Lat", fontsize=8)
        mv = float(np.nanmean(dm))
        ax.text(0.03, 0.04, f"{mv:.4f}",
                transform=ax.transAxes, fontsize=7,
                color="white", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2",
                          facecolor="black", alpha=0.5))

    fig.suptitle(
        f"{title_suffix} | {SCENARIO_LABELS[selected_scenario]}",
        fontsize=11, fontweight="bold"
    )
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close()

# ══════════════════════════════════════════════════════════════════════
# PAGE: RIVER BASINS
# ══════════════════════════════════════════════════════════════════════
elif page == "🌊 River Basins":
    st.title("River Basin Analysis")
    st.caption(
        "Projected change in spring snowmelt by 2090s | "
        "3-model ensemble mean"
    )

    # ── Basin summary cards ──
    cols = st.columns(len(BASINS))
    for col, (bname, binfo) in zip(cols, BASINS.items()):
        pcts = get_basin_pcts(bname)
        col.markdown(
            f"<div style='border-left:4px solid {binfo['color']};"
            f"padding:8px;border-radius:4px;'>"
            f"<b>{bname}</b><br>"
            f"<small>{binfo['desc']}</small><br><br>"
            f"<b style='color:{SC_COL['ssp245']}'>"
            f"SSP2-4.5: +{pcts['ssp245']['mean']:.0f}%</b><br>"
            f"<b style='color:{SC_COL['ssp585']}'>"
            f"SSP5-8.5: +{pcts['ssp585']['mean']:.0f}%</b>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.divider()
    col_ts, col_bar = st.columns([3, 2])

    with col_ts:
        st.subheader(f"{selected_basin} — Time series")
        st.caption(BASINS[selected_basin]["desc"])
        mask = basin_masks[selected_basin]

        fig, ax = plt.subplots(figsize=(10, 5))
        basin_col = BASINS[selected_basin]["color"]

        for sc in SCENARIOS:
            ann_vals = []
            for m in MODELS:
                res  = results[m][sc]
                dm   = res["decade_maps"]
                # Scale factor per decade
                ts   = pd.Series(res["melt_mean"], index=res["times"])
                ann  = ts.resample("YE").mean()
                yrs  = ann.index.year

                # Simple: use domain-mean time series scaled by basin/domain ratio
                # from 2030s decadal map
                basin_mean = np.nanmean(dm["2030s"][mask])
                domain_mean = np.nanmean(dm["2030s"][np.isfinite(dm["2030s"])])
                scale = basin_mean / max(domain_mean, 1e-6)
                ann_vals.append(ann.values * scale)

            arr = np.array(ann_vals)
            ens = arr.mean(0)
            ax.fill_between(yrs, arr.min(0), arr.max(0),
                            alpha=0.15, color=SC_COL[sc])
            ax.plot(yrs, ens, color=SC_COL[sc], linewidth=2,
                    linestyle="-" if sc == "ssp585" else "--",
                    label=SCENARIO_LABELS[sc])

        base_val = float(
            results[MODELS[0]]["ssp245"]["melt_mean"][:3].mean()
        )
        ax.axhline(base_val, color="gray", linewidth=1,
                   linestyle=":", alpha=0.7, label="Baseline")
        ax.set_xlabel("Year", fontsize=10)
        ax.set_ylabel("Melt (mm/day)", fontsize=10)
        ax.set_xlim(2024, 2100)
        ax.set_title(
            f"{selected_basin}\nSolid = SSP5-8.5 | Dashed = SSP2-4.5",
            fontsize=11, fontweight="bold",
            color=BASINS[selected_basin]["color"]
        )
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        st.pyplot(fig, use_container_width=True)
        plt.close()

    with col_bar:
        st.subheader("All basins — 2090s change")
        bnames  = list(BASINS.keys())
        bcolors = [BASINS[b]["color"] for b in bnames]

        fig, ax = plt.subplots(figsize=(7, 6))
        x      = np.arange(len(bnames))

        p245 = [get_basin_pcts(b)["ssp245"]["mean"] for b in bnames]
        p585 = [get_basin_pcts(b)["ssp585"]["mean"] for b in bnames]

        ax.barh(x + 0.2, p245, 0.35,
                color=SC_COL["ssp245"], alpha=0.75, label="SSP2-4.5")
        ax.barh(x - 0.2, p585, 0.35,
                color=SC_COL["ssp585"], alpha=0.85, label="SSP5-8.5")

        for i, (v245, v585) in enumerate(zip(p245, p585)):
            ax.text(v585+0.3, i-0.2, f"+{v585:.0f}%",
                    va="center", fontsize=8, fontweight="bold",
                    color=SC_COL["ssp585"])
            ax.text(v245+0.3, i+0.2, f"+{v245:.0f}%",
                    va="center", fontsize=8,
                    color=SC_COL["ssp245"])

        ax.set_yticks(x)
        ax.set_yticklabels([b.replace("Sacramento-San Joaquin",
                                      "Sacramento-SJ")
                            for b in bnames], fontsize=9)
        ax.set_xlabel("Change by 2090s (%)", fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="x")
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_title("Basin % Change vs 2024–2026",
                     fontsize=11, fontweight="bold")
        st.pyplot(fig, use_container_width=True)
        plt.close()

    # ── Emissions gap table ──
    st.subheader("The emissions gap — what mitigation controls")
    st.caption(
        "Difference between SSP5-8.5 and SSP2-4.5 by 2090s. "
        "This is the range of outcomes that climate policy determines."
    )
    rows = []
    for bname in bnames:
        pcts = get_basin_pcts(bname)
        gap  = pcts["ssp585"]["mean"] - pcts["ssp245"]["mean"]
        rows.append({
            "Basin":        bname,
            "SSP2-4.5 (%)": f"+{pcts['ssp245']['mean']:.0f}",
            "SSP5-8.5 (%)": f"+{pcts['ssp585']['mean']:.0f}",
            "Emissions gap (pp)": f"{gap:.0f}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True,
                 hide_index=True)

# ══════════════════════════════════════════════════════════════════════
# PAGE: ABOUT
# ══════════════════════════════════════════════════════════════════════
elif page == "ℹ️ About":
    st.title("About this project")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("""
## Physics-Informed Snowmelt Emulator

This dashboard presents snowmelt projections for the western United States
from 2024 to 2100, generated by a physics-informed neural network (PINN)
forced with bias-corrected CMIP6 climate data.

### Three-phase project

**Phase 1 — Colorado Rockies**
Proof-of-concept PINN trained on 12 SNOTEL stations (2000–2023).
Physics constraints reduce physics violations by 51% and improve
out-of-distribution robustness 6× on record-heat years.

**Phase 2 — Western US (654 stations)**
Scale-up to 5.67 million station-days across 11 western states.
Spatial cross-validation shows PINN improves by 16.1% in sparse
snowpack regimes (AZ+NM). Monte Carlo uncertainty maps identify
Pacific Northwest as highest-uncertainty region.

**Phase 3 — CMIP6 Projections (this dashboard)**
The trained PINN is forced with bias-corrected CMIP6 projections
from three models across two emissions scenarios. 76-year melt
trajectories aggregated to five major river basins.

### Key findings
- SSP2-4.5: +12–21% melt increase by 2090s (basin range)
- SSP5-8.5: +27–62% melt increase by 2090s
- Columbia and Missouri headwaters most sensitive (+60%)
- Emissions gap of 14–41 percentage points across basins
- CanESM5 (high sensitivity) brackets the upper uncertainty bound
""")

    with col2:
        st.markdown("### Technical details")
        st.markdown("""
| Component | Detail |
|-----------|--------|
| Architecture | 6→128→128→64→1 MLP |
| Parameters | 25,025 |
| Training data | 5.67M station-days |
| Training period | 2000–2015 |
| Climate forcing | ERA5-Land 0.1° |
| Bias correction | Delta method |
| Reference period | 1985–2014 |
| CMIP6 models | MRI, GFDL, CanESM5 |
| Scenarios | SSP2-4.5, SSP5-8.5 |
| Projection period | 2024–2100 |
| Grid | 191×231 = 44,121 pts |
""")
        st.divider()
        st.markdown("### Physics constraints")
        st.latex(r"""
\mathcal{L} = \mathcal{L}_{MSE}
+ \lambda_1 \mathbb{E}[\max(-M, 0)^2]
""")
        st.latex(r"""
+ \lambda_2 \mathbb{E}[\max(M - \text{SWE}, 0)^2]
""")
        st.latex(r"""
+ \lambda_3 \mathbb{E}[\max(M - M_{\text{energy}}, 0)^2]
""")
        st.caption(
            "λ₁=1.0, λ₂=5.0, λ₃=0.5 | "
            "Tuned by grid search"
        )
        st.divider()
        st.markdown("### Data sources")
        st.markdown("""
- **ERA5-Land:** Copernicus CDS
- **CMIP6:** Copernicus CDS
- **SNOTEL:** USDA NRCS
""")

    st.divider()
    st.markdown("""
### Citation
*Pradhan, I.P. (2026). Physics-informed neural networks for continental-scale
snowmelt emulation.*

### Repositories
- [snowmelt-pinn](https://github.com/IpshitaPPradhan/snowmelt-pinn) — Phase 1
- [snowmelt-pinn-v2](https://github.com/IpshitaPPradhan/snowmelt-pinn-v2) — Phase 2
- [snowmelt-pinn-v3](https://github.com/IpshitaPPradhan/snowmelt-pinn-v3) — Phase 3
""")

# ── Footer ─────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Physics-Informed Snowmelt Emulator | "
    "Ipshita P. Pradhan | "
    "PINN v2 + ERA5-Land + CMIP6 | "
    "Western US 2024–2100"
)