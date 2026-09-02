# The one house style for every figure in this repository. Plot scripts source this file
# and take their colours and theme from it; restyle here, never inline in a script.
#
#   source("docs/theme.R")
#   pal <- panel_palette("light")          # or "dark"
#   p + theme_panel("light")
#   panel_save(p, "docs/figure-light.png", "light")
#
# Two modes because the README serves each figure through <picture> with a
# prefers-color-scheme source, so every figure is rendered twice from the same script.

library(ggplot2)

panel_palette <- function(mode = c("light", "dark")) {
  mode <- match.arg(mode)
  if (mode == "light") {
    list(surface = "#fcfcfb", ink = "#0b0b0b", ink2 = "#52514e", muted = "#898781",
         grid = "#e1e0d9", axis = "#c3c2b7",
         series = c("#2a78d6", "#eb6834", "#1baf7a"))
  } else {
    list(surface = "#1a1a19", ink = "#ffffff", ink2 = "#c3c2b7", muted = "#898781",
         grid = "#2c2c2a", axis = "#383835",
         series = c("#3987e5", "#d95926", "#199e70"))
  }
}

panel_font <- "DejaVu Sans"

theme_panel <- function(mode = c("light", "dark"), base_size = 10) {
  pal <- panel_palette(mode)
  theme_minimal(base_size = base_size, base_family = panel_font) +
    theme(
      plot.background = element_rect(fill = pal$surface, colour = NA),
      panel.background = element_rect(fill = pal$surface, colour = NA),
      panel.grid.major = element_line(colour = pal$grid, linewidth = 0.35),
      panel.grid.minor = element_blank(),
      axis.line = element_line(colour = pal$axis, linewidth = 0.4),
      axis.ticks = element_blank(),
      axis.text = element_text(colour = pal$muted, size = base_size * 0.9),
      # 0.86: a one-line y title must fit the panel's height, not the figure's
      axis.title = element_text(colour = pal$ink2, size = base_size * 0.86),
      axis.title.y = element_text(margin = margin(r = 8)),
      axis.title.x = element_text(margin = margin(t = 8)),
      plot.title = element_text(colour = pal$ink, size = base_size * 1.05, face = "plain",
                                hjust = 0, margin = margin(b = 4)),
      plot.subtitle = element_text(colour = pal$ink2, size = base_size * 0.9, hjust = 0,
                                   margin = margin(b = 12)),
      plot.title.position = "plot",
      legend.position = "inside",
      legend.position.inside = c(0.01, 0.02),
      legend.justification = c(0, 0),
      legend.background = element_blank(),
      legend.key = element_blank(),
      legend.title = element_blank(),
      legend.text = element_text(colour = pal$ink2, size = base_size * 0.9),
      legend.key.size = unit(10, "pt"),
      plot.margin = margin(12, 16, 10, 12)
    )
}

# Same canvas as the README's other figures: 6.2 x 4.0 in at 200 dpi.
panel_save <- function(p, path, mode = c("light", "dark"), width = 6.2, height = 4.0, dpi = 200) {
  pal <- panel_palette(mode)
  ragg::agg_png(path, width = width, height = height, units = "in", res = dpi, background = pal$surface)
  print(p)
  invisible(dev.off())
  cat("wrote", path, "\n")
}
