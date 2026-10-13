-- One row per day; the most recently ingested value wins because NOAA revises recent days.
with latest as (
    select * from {{ ref('stg_weather') }}
    qualify row_number() over (partition by obs_date, datatype order by _ingested_at desc) = 1
)
select
    obs_date,
    max(value) filter (where datatype = 'TMAX') as temp_max_f,
    max(value) filter (where datatype = 'TMIN') as temp_min_f,
    max(value) filter (where datatype = 'PRCP') as precip_in,
    max(value) filter (where datatype = 'SNOW') as snow_in,
    max(value) filter (where datatype = 'AWND') as wind_avg_mph
from latest
group by obs_date
