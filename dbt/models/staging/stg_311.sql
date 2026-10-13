-- Typed view over raw 311 rows. Every version of a request is still here.
select
    sr_number,
    upper(trim(sr_type))                                   as sr_type,
    coalesce(nullif(upper(trim(sr_type_desc)), ''), 'UNKNOWN') as sr_type_desc,  -- a few requests arrive with no type
    upper(trim(dept_name))                                 as dept_name,
    upper(trim(dept_division))                             as dept_division,
    upper(trim(neighborhood))                              as neighborhood,
    nullif(trim(zipcode), '')                              as zipcode,
    upper(trim(method_received))                           as method_received,
    upper(trim(sr_status))                                 as sr_status,
    try_cast(date_created as timestamp)::date              as created_date,
    try_strptime(left(date_created, 10) || ' ' || time_received, '%Y-%m-%d %I:%M %p') as created_at,
    try_cast(date_closed as timestamp)::date               as closed_date,
    try_strptime(left(date_last_update, 10) || ' ' || coalesce(time_last_update, '12:00 AM'), '%Y-%m-%d %I:%M %p')
                                                           as last_updated_at,
    try_cast(planned_completion_days as double)            as planned_completion_days,
    try_cast(latitude as double)                           as latitude,
    try_cast(longitude as double)                          as longitude,
    _batch_id,
    _ingested_at
from {{ source('raw', 'cincy_311') }}
