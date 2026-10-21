-- Analysis-ready ROI metrics, one row per institution with 10-year earnings.
--
--   earnings_10yr_adj   earnings divided by the school's state price index
--                       (BEA RPP), i.e. in "national-average dollars"
--   debt_to_earnings    median completer debt / median 10-yr earnings
--   payback_years       years to repay median debt paying 10% of earnings
--                       (interest ignored: a simple, explainable proxy)
--   net_cost_4yr        average annual net price x 4
--   earnings_per_cost   10-yr earnings / 4-yr net cost

with base as (
    select i.*, r.price_index
    from {{ ref('stg_institutions') }} i
    left join {{ ref('stg_state_rpp') }} r using (state)
    where i.earnings_10yr is not null
      and i.earnings_10yr > 0
)

select
    unitid,
    name,
    city,
    state,
    region_id,
    ownership,
    is_hbcu,
    lat,
    lon,
    enrollment,
    admission_rate,
    sat_avg,
    pell_rate,
    grad_rate,
    retention_rate,
    net_price,
    median_debt,
    earnings_6yr,
    earnings_10yr,
    price_index,
    price_index is not null                                        as has_price_index,
    round(earnings_10yr / coalesce(price_index, 1.0), 0)           as earnings_10yr_adj,
    round(median_debt / earnings_10yr, 3)                          as debt_to_earnings,
    round(median_debt / (0.10 * earnings_10yr), 1)                 as payback_years,
    net_price * 4                                                  as net_cost_4yr,
    round(earnings_10yr / nullif(net_price * 4, 0), 2)             as earnings_per_cost,
    round(percent_rank() over (order by earnings_10yr), 3)         as earnings_pctile,
    round(percent_rank() over (
        partition by ownership order by earnings_10yr), 3)         as earnings_pctile_in_sector
from base
