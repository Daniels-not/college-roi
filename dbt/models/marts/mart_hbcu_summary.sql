-- Raw HBCU vs. non-HBCU medians. Uncontrolled on purpose: the value-added
-- model (src/scorecard/models.py) produces the controlled comparison.

select
    case when is_hbcu then 'HBCU' else 'Non-HBCU' end   as group_name,
    count(*)                                            as n_schools,
    median(earnings_10yr)                               as median_earnings_10yr,
    median(earnings_10yr_adj)                           as median_earnings_10yr_adj,
    median(median_debt)                                 as median_debt,
    median(debt_to_earnings)                            as median_debt_to_earnings,
    median(pell_rate)                                   as median_pell_rate,
    median(grad_rate)                                   as median_grad_rate
from {{ ref('mart_institution_roi') }}
group by 1
order by 1
