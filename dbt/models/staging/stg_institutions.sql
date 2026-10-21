-- Type-safe, human-readable institution table.
-- TRY_CAST turns anything non-numeric (e.g. 'PrivacySuppressed' in the bulk
-- CSVs) into NULL instead of failing the whole build.

select
    cast(unitid as integer)                              as unitid,
    trim(name)                                           as name,
    city,
    upper(state)                                         as state,
    try_cast(region_id as integer)                       as region_id,
    try_cast(locale as integer)                          as locale,
    try_cast(ownership as integer)                       as ownership_code,
    case try_cast(ownership as integer)
        when 1 then 'Public'
        when 2 then 'Private nonprofit'
        when 3 then 'Private for-profit'
    end                                                  as ownership,
    coalesce(try_cast(is_hbcu as integer), 0) = 1        as is_hbcu,
    try_cast(lat as double)                              as lat,
    try_cast(lon as double)                              as lon,
    try_cast(enrollment as integer)                      as enrollment,
    try_cast(admission_rate as double)                   as admission_rate,
    try_cast(sat_avg as double)                          as sat_avg,
    try_cast(tuition_in_state as double)                 as tuition_in_state,
    try_cast(tuition_out_of_state as double)             as tuition_out_of_state,
    -- Net price is published in separate public/private columns; only one is
    -- populated per school, so merge them into a single measure.
    coalesce(try_cast(net_price_public as double),
             try_cast(net_price_private as double))      as net_price,
    try_cast(pell_rate as double)                        as pell_rate,
    try_cast(federal_loan_rate as double)                as federal_loan_rate,
    try_cast(median_debt_completers as double)           as median_debt,
    try_cast(grad_rate_150 as double)                    as grad_rate,
    try_cast(retention_rate as double)                   as retention_rate,
    try_cast(earnings_6yr_median as double)              as earnings_6yr,
    try_cast(earnings_10yr_median as double)             as earnings_10yr,
    _loaded_at
from {{ source('scorecard', 'raw_institutions') }}
where unitid is not null
