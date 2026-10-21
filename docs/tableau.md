# Tableau Public / Power BI version

Many analyst job postings list Tableau or Power BI by name. This guide rebuilds
the main dashboard there from the CSVs the pipeline already exports, so you
can show both "I can code it" and "I can build it in your BI tool."

## 1. Get the data

`python -m scorecard all` (or `export`) writes these to `exports/tableau/`:

| File | Grain | Use |
|---|---|---|
| `schools.csv` | one row per school | main data source |
| `model_coefficients.csv` | one row per model term | HBCU gap chart |
| `peer_group_profile.csv` | one row per peer group | peer-group table |
| `hbcu_summary.csv` | HBCU vs. non-HBCU | raw comparison |

## 2. Tableau Public (free)

1. Download Tableau Public Desktop: <https://public.tableau.com/app/discover>.
2. **Connect → Text file →** `exports/tableau/schools.csv`.
3. On the Data Source tab, check that `lat`/`lon` are geographic roles
   (Latitude/Longitude) and `state` is State/Province.

### Sheets to build

**A. Value-added ranking (bar)**
- Rows: `name` · Columns: `value_added_pct`
- Filter: `value_added_rank` ≤ 15 (add a second copy filtered to the bottom 15)
- Color: calculated field `IF [value_added_pct] >= 0 THEN "Above" ELSE "Below" END`
  → Above `#2a78d6`, Below `#e34948`
- Label: `value_added_pct`, formatted as percent with a + sign

**B. Map**
- Double-click `lat` and `lon` · Detail: `name`
- Color: `value_added_pct`, *Diverging* palette, center 0, blue/red
- Tooltip: name, state, `earnings_10yr_adj`, `predicted_earnings_adj`, `value_added_pct`

**C. Earnings vs. cost scatter**
- Columns: `net_price` · Rows: `earnings_10yr_adj` · Detail: `name`
- Color: `peer_group_label` (or highlight one group with a parameter, as the Streamlit app does)

**D. HBCU gap (dot + CI)**
- New data source: `model_coefficients.csv`, filter `term = is_hbcu`
- Rows: `model` · Columns: `pct_effect`
- Add `ci_low`/`ci_high` (convert with `EXP([ci_low]) - 1`) as a reference band or error bars

**E. KPI tiles**
- Separate sheets showing `MEDIAN([earnings_10yr_adj])`, `MEDIAN([median_debt])`,
  `MEDIAN([payback_years])`, `COUNTD([unitid])`

### Dashboard
- Size: Automatic · Layout: KPIs on top, map + ranking in the middle, scatter below
- Add filters for `state`, `ownership`, and `is_hbcu` and set them to **Apply to all worksheets**
- Use the *Highlight* action from the map to the scatter

### Publish
**File → Save to Tableau Public**. Put the link in your README and your resume.

## 3. Power BI (alternative)

Get Data → Text/CSV → `schools.csv`. Use the built-in Map visual (lat/lon), a
clustered bar for the ranking, and a scatter for earnings vs. net price. Publish
to the web from Power BI Service (needs a work/school account; your Oakwood
email should work).

## Tips that recruiters notice
- Title every chart with the *finding*, not the metric ("Selective schools aren't always the best value").
- Put a one-line "How to read this" caption under the value-added chart.
- Cite the data source and date in the dashboard footer.
