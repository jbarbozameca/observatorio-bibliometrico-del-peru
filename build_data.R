# =====================================================================
#  Preprocesamiento para el dashboard interactivo
#  Genera data/data.js con agregados por INVESTIGADOR e INSTITUCIÓN.
# =====================================================================
suppressMessages({library(data.table); library(jsonlite); library(stringr)})

base   <- "/Users/joshuanbarbozameca/Library/Mobile Documents/com~apple~CloudDocs/7. CONFERENCES/2. YOUTUBE PREMIUM/1. CONFERENCIAS 2026. SEMANALES/7. MEDIR RANKING UNIVERSITARIOS"
csv_in <- file.path(base, "Publications_in_Peru_2020_-_2025.csv")
outdir <- file.path(base, "dashboard", "data")
dir.create(outdir, showWarnings = FALSE, recursive = TRUE)

MIN_PUBS_AUTHOR <- 5   # umbral para incluir investigadores
MIN_PUBS_INST   <- 5   # umbral para incluir instituciones

numify <- function(x) suppressWarnings(as.numeric(x))
dt <- fread(csv_in, skip = 19, header = TRUE, encoding = "UTF-8",
            quote = "\"", fill = TRUE, showProgress = FALSE)

core <- data.table(
  pid       = seq_len(nrow(dt)),
  year      = suppressWarnings(as.integer(dt$Year)),
  citations = numify(dt$Citations),
  fwci      = numify(dt$`Field-Weighted Citation Impact`),
  cs_pct    = numify(dt$`CiteScore percentile (publication year) *`),
  top_pctl  = numify(dt$`Outputs in Top Citation Percentiles, per percentile`),
  ncountry  = numify(dt$`Number of Countries/Regions`),
  oa_raw    = dt$`Open Access`,
  authors   = dt$Authors,
  ids       = dt$`Scopus Author Ids`,
  insts     = dt$Institutions,
  asjc      = dt$`All Science Journal Classification (ASJC) field name`
)
core <- core[!is.na(year) & year >= 2020 & year <= 2025]

core[, `:=`(
  oa_any   = !(is.na(oa_raw) | oa_raw %in% c("", "-")),
  intl     = ncountry > 1,
  in_top10 = !is.na(top_pctl) & top_pctl <= 10 & top_pctl > 0,
  is_q1    = !is.na(cs_pct) & cs_pct >= 75,
  area1    = str_trim(tstrsplit(asjc, "\\|", fixed = FALSE)[[1]])
)]
core[is.na(area1) | area1 %in% c("", "-"), area1 := "Sin clasificar"]

# ---- Función de agregación por entidad -----------------------------
agg_entity <- function(long) {
  # long: data.table con columna 'key' (id/nombre) + 'label' + métricas por pid
  ag <- long[, .(
    n_pubs = .N,
    cit_total = round(sum(citations, na.rm = TRUE)),
    cit_mean  = round(mean(citations, na.rm = TRUE), 1),
    fwci_mean = round(mean(fwci, na.rm = TRUE), 2),
    pct_top10 = round(mean(in_top10) * 100, 1),
    pct_oa    = round(mean(oa_any) * 100, 1),
    pct_intl  = round(mean(intl, na.rm = TRUE) * 100, 1),
    pct_q1    = round(mean(is_q1) * 100, 1),
    y2020 = sum(year == 2020), y2021 = sum(year == 2021),
    y2022 = sum(year == 2022), y2023 = sum(year == 2023),
    y2024 = sum(year == 2024), y2025 = sum(year == 2025)
  ), by = key]
  # etiqueta más frecuente
  lab <- long[, .N, by = .(key, label)][order(-N)][, .SD[1], by = key][, .(key, label)]
  # top 4 áreas
  ar <- long[, .N, by = .(key, area1)][order(key, -N)][
    , head(.SD, 4), by = key][, .(areas = paste(area1, collapse = "; ")), by = key]
  ag <- merge(ag, lab, by = "key")
  ag <- merge(ag, ar, by = "key")
  ag[]
}

# =====================================================================
#  INVESTIGADORES (por Scopus Author ID)
# =====================================================================
ca <- core[!is.na(ids) & ids != "" & ids != "-"]
auth_long <- ca[, {
  nm <- str_trim(strsplit(authors, "\\|")[[1]])
  id <- str_trim(strsplit(ids, "\\|")[[1]])
  k  <- min(length(nm), length(id))
  list(key = id[seq_len(k)], label = nm[seq_len(k)])
}, by = .(pid, year, citations, fwci, oa_any, intl, in_top10, is_q1, area1)]
auth_long <- auth_long[key != "" & !is.na(key)]
cat("Author-paper rows:", nrow(auth_long), "\n")

res <- agg_entity(auth_long)
res <- res[n_pubs >= MIN_PUBS_AUTHOR][order(-n_pubs)]
cat("Investigadores (>=", MIN_PUBS_AUTHOR, "pubs):", nrow(res), "\n")

# =====================================================================
#  INSTITUCIONES
# =====================================================================
ci <- core[!is.na(insts) & insts != "" & insts != "-"]
inst_long <- ci[, {
  v <- str_trim(strsplit(insts, "\\|")[[1]])
  list(key = v, label = v)
}, by = .(pid, year, citations, fwci, oa_any, intl, in_top10, is_q1, area1)]
inst_long <- inst_long[key != "" & key != "-" & !is.na(key)]
cat("Institution-paper rows:", nrow(inst_long), "\n")

ins <- agg_entity(inst_long)
ins <- ins[n_pubs >= MIN_PUBS_INST][order(-n_pubs)]
cat("Instituciones (>=", MIN_PUBS_INST, "pubs):", nrow(ins), "\n")

# =====================================================================
#  Serialización a JS (autocontenido, sin fetch/CORS)
# =====================================================================
to_records <- function(d) {
  setnames(d, "key", "id")
  d[, .(id, name = label, n_pubs, cit_total, cit_mean, fwci_mean,
        pct_top10, pct_oa, pct_intl, pct_q1,
        y = sprintf("[%d,%d,%d,%d,%d,%d]", y2020, y2021, y2022, y2023, y2024, y2025),
        areas)]
}
res_j <- to_records(copy(res))
ins_j <- to_records(copy(ins))

# JSON con arrays de años como números reales (no string)
res_json <- toJSON(res_j, dataframe = "rows", auto_unbox = TRUE)
ins_json <- toJSON(ins_j, dataframe = "rows", auto_unbox = TRUE)
res_json <- gsub('"y":"(\\[[0-9,]+\\])"', '"y":\\1', res_json)
ins_json <- gsub('"y":"(\\[[0-9,]+\\])"', '"y":\\1', ins_json)

# Totales nacionales para contexto / línea de referencia
nat <- list(
  total_pubs = nrow(core),
  fwci_mean  = round(mean(core$fwci, na.rm = TRUE), 2),
  pct_oa     = round(mean(core$oa_any) * 100, 1),
  pct_intl   = round(mean(core$intl, na.rm = TRUE) * 100, 1),
  pct_top10  = round(mean(core$in_top10) * 100, 1),
  pct_q1     = round(mean(core$is_q1) * 100, 1),
  by_year    = as.integer(table(factor(core$year, levels = 2020:2025)))
)
nat_json <- toJSON(nat, auto_unbox = TRUE)

js <- paste0(
  "// Datos generados con build_data.R — Fuente: Scopus/SciVal (mayo 2026)\n",
  "window.NATIONAL = ", nat_json, ";\n",
  "window.RESEARCHERS = ", res_json, ";\n",
  "window.INSTITUTIONS = ", ins_json, ";\n"
)
writeLines(js, file.path(outdir, "data.js"), useBytes = TRUE)

sz <- file.info(file.path(outdir, "data.js"))$size
cat("data.js generado:", round(sz/1024/1024, 2), "MB\n")
cat("Listo.\n")
