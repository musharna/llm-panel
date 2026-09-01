"""AACR-Bench prompt-style results as a precision/recall plane. Numbers are the README
table (extractor-3 re-measurements, 18 PRs, 2026-08-28); the recall error bar is the
measured re-run floor: +-3 of 150 reference matches = +-2.0 pp."""
import signal, sys
signal.signal(signal.SIGALRM, lambda *_: (sys.stderr.write("aborting: walltime guard\n"), sys.exit(2)))
signal.alarm(60)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ARMS = [  # name, recall %, precision %, findings read per validated hit, slot
    ("defect", 12.2, 16.5, 6.1),
    ("broad", 26.0, 13.2, 7.6),
    ("volume", 25.2, 7.9, 12.6),
]
FLOOR = 2.0  # pp, recall

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
                  grid="#e1e0d9", axis="#c3c2b7",
                  series=["#2a78d6", "#eb6834", "#1baf7a"]),
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
                 grid="#2c2c2a", axis="#383835",
                 series=["#3987e5", "#d95926", "#199e70"]),
}

def render(mode, out):
    t = THEMES[mode]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, ax = plt.subplots(figsize=(6.2, 4.0), dpi=200)
    fig.patch.set_facecolor(t["surface"]); ax.set_facecolor(t["surface"])
    for i, (name, rec, prec, reads) in enumerate(ARMS):
        c = t["series"][i]
        ax.errorbar(prec, rec, yerr=FLOOR, fmt="none", ecolor=c, elinewidth=1.2,
                    capsize=3, capthick=1.2, alpha=0.9, zorder=2)
        ax.scatter([prec], [rec], s=80, color=c, edgecolor=t["surface"], linewidth=2,
                   zorder=3, label=name)
        label = f"{name} (default)" if name == "defect" else name
        if name == "volume":
            # broad's error bar sits to its right and the axis to its left: stack the
            # labels above and below its own error bar instead.
            pos = [((0, 18), "center", "bottom"), ((0, -18), "center", "top")]
        else:
            pos = [((11, 5), "left", "center"), ((11, -8), "left", "center")]
        (d1, h1, v1), (d2, h2, v2) = pos
        ax.annotate(label, (prec, rec), xytext=d1, textcoords="offset points",
                    color=t["ink"], fontsize=10.5, fontweight="bold", ha=h1, va=v1)
        ax.annotate(f"{reads} findings read per hit", (prec, rec),
                    xytext=d2, textcoords="offset points",
                    color=t["ink2"], fontsize=9.5, ha=h2, va=v2)
    ax.set_xlim(4, 22); ax.set_ylim(0, 32)
    ax.set_xticks(range(5, 21, 5)); ax.set_yticks(range(0, 31, 10))
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_xlabel("precision  (findings upstream's evaluator validated)", color=t["ink2"], fontsize=9.5)
    ax.set_ylabel("semantic recall  (human review comments matched)", color=t["ink2"], fontsize=9.5)
    ax.grid(True, color=t["grid"], linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(t["axis"])
    ax.tick_params(colors=t["muted"], labelsize=9, length=0)
    ax.set_title("--prompt-style on 18 AACR-Bench PRs, scored by upstream's evaluator",
                 loc="left", color=t["ink"], fontsize=10.5, pad=22)
    ax.text(0, 1.03, f"bars: ±{FLOOR:.0f} pp recall — the measured re-run noise floor "
            "(±3 of 150 matches)",
            transform=ax.transAxes, color=t["ink2"], fontsize=9, va="bottom")
    ax.legend(loc="lower left", frameon=False, fontsize=9, labelcolor=t["ink2"],
              handletextpad=0.4, borderaxespad=0.6)
    fig.tight_layout()
    fig.savefig(out, facecolor=t["surface"])
    print("wrote", out)

if __name__ == "__main__":
    import pathlib
    d = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(".")
    render("light", d / "bench-light.png")
    render("dark", d / "bench-dark.png")
