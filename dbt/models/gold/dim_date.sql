-- Calendar from the earliest request in the data (old requests still get updated) to today.
with bounds as (
    select least(coalesce(min(created_date), date '2020-01-01'), date '2020-01-01') as first_day
    from {{ ref('svc_requests') }}
)
select
    d::date                           as date_key,
    year(d)                           as year,
    month(d)                          as month,
    strftime(d, '%b')                 as month_name,
    dayofweek(d)                      as day_of_week,
    strftime(d, '%a')                 as day_name,
    dayofweek(d) in (0, 6)            as is_weekend
from bounds, range(bounds.first_day, current_date + interval 1 day, interval 1 day) t(d)
