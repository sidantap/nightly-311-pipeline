-- Daily request volume by category, next to that day's weather.
select
    f.created_date_key                as day,
    t.category,
    count(*)                          as requests,
    w.temp_max_f,
    w.temp_min_f,
    w.precip_in,
    w.snow_in
from {{ ref('fct_service_requests') }} f
join {{ ref('dim_request_type') }} t using (request_type_key)
left join {{ ref('weather_daily') }} w on w.obs_date = f.created_date_key
group by all
