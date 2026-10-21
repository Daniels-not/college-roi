-- BEA Regional Price Parities, 2023 (U.S. average = 100).
-- Source: BEA release 24-59, Dec 12 2024, Table 2.

select
    upper(state)          as state,
    state_name,
    rpp_2023 / 100.0      as price_index
from {{ ref('state_rpp') }}
