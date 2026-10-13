select
    cast(date as timestamp)::date as obs_date,
    datatype,
    value,
    _ingested_at
from {{ source('raw', 'weather_daily') }}
