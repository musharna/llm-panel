#!/usr/bin/env Rscript
# AACR-Bench prompt-style results as a precision/recall plane. Numbers are the README
# table (extractor-3 re-measurements, 18 PRs, 2026-08-28); the recall error bar is the
# measured re-run floor: +-3 of 150 reference matches = +-2.0 pp.
#
#   Rscript docs/bench_chart.R [outdir]     # writes bench-light.png and bench-dark.png
setTimeLimit(elapsed = 120, transient = TRUE)

script_dir <- dirname(sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1]))
source(file.path(script_dir, "theme.R"))

FLOOR <- 2.0  # pp, recall

arms <- data.frame(
  name      = c("defect", "broad", "volume"),
  recall    = c(12.2, 26.0, 25.2),
  precision = c(16.5, 13.2, 7.9),
  reads     = c(6.1, 7.6, 12.6),
  stringsAsFactors = FALSE
)
arms$name <- factor(arms$name, levels = arms$name)
arms$label <- ifelse(arms$name == "defect", "defect (default)", as.character(arms$name))
arms$reads_label <- sprintf("%.1f findings read per hit", arms$reads)

# Label placement in data units. defect and broad sit to the right of their point; volume
# has broad's error bar to its right and the axis to its left, so its two labels stack
# above and below its own error bar instead.
right <- arms$name != "volume"
arms$lx  <- ifelse(right, arms$precision + 0.6, arms$precision)
arms$ly1 <- ifelse(right, arms$recall + 0.35, arms$recall + FLOOR + 0.9)
arms$ly2 <- ifelse(right, arms$recall - 0.75, arms$recall - FLOOR - 0.9)
arms$hj  <- ifelse(right, 0, 0.5)

render <- function(mode, out) {
  pal <- panel_palette(mode)
  p <- ggplot(arms, aes(precision, recall, colour = name)) +
    geom_errorbar(aes(ymin = recall - FLOOR, ymax = recall + FLOOR),
                  width = 0.45, linewidth = 0.55, alpha = 0.9) +
    geom_point(aes(fill = name), shape = 21, size = 4.2, stroke = 1.1, colour = pal$surface) +
    geom_text(aes(lx, ly1, label = label, hjust = hj), vjust = 0,
              colour = pal$ink, family = panel_font, fontface = "bold", size = 3.7) +
    geom_text(aes(lx, ly2, label = reads_label, hjust = hj), vjust = 1,
              colour = pal$ink2, family = panel_font, size = 3.3) +
    scale_colour_manual(values = pal$series, aesthetics = c("colour", "fill"),
                        labels = levels(arms$name)) +
    scale_x_continuous(breaks = seq(5, 20, 5), labels = function(v) paste0(v, "%")) +
    scale_y_continuous(breaks = seq(0, 30, 10), labels = function(v) paste0(v, "%")) +
    coord_cartesian(xlim = c(4, 22), ylim = c(0, 32), expand = FALSE, clip = "off") +
    labs(x = "precision  (findings upstream's evaluator validated)",
         y = "semantic recall  (human review comments matched)",
         title = "--prompt-style on 18 AACR-Bench PRs, scored by upstream's evaluator",
         subtitle = sprintf("bars: ±%.0f pp recall — the measured re-run noise floor (±3 of 150 matches)", FLOOR)) +
    guides(colour = guide_legend(override.aes = list(shape = 16, colour = pal$series, size = 3, linetype = 0))) +
    theme_panel(mode)
  panel_save(p, out, mode)
}

args <- commandArgs(trailingOnly = TRUE)
outdir <- if (length(args) >= 1) args[1] else "."
render("light", file.path(outdir, "bench-light.png"))
render("dark", file.path(outdir, "bench-dark.png"))
