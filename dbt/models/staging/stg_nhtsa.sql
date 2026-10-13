select
    odino                                         as complaint_id,
    upper(trim(component))                        as component,
    upper(trim(split_part(component, ':', 1)))    as component_prefix,
    upper(trim(make))                             as make,
    upper(trim(model))                            as model,
    try_cast(model_year as integer)               as model_year,
    crash = 'Y'                                   as crash,
    fire = 'Y'                                    as fire,
    try_cast(injured as integer)                  as injured,
    try_cast(deaths as integer)                   as deaths,
    upper(trim(state))                            as state,
    try_strptime(date_received, '%Y%m%d')::date   as received_date,
    try_strptime(date_added, '%Y%m%d')::date      as added_date,
    trim(description)                             as description,
    _ingested_at
from {{ source('raw', 'nhtsa_complaints') }}
