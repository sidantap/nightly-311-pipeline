-- One row per 311 request, keyed to its dimensions.
select
    r.sr_number,
    r.created_date                                       as created_date_key,
    r.closed_date                                        as closed_date_key,
    t.request_type_key,
    r.neighborhood,
    r.method_received,
    r.sr_status,
    r.status_group,
    r.status_group = 'open'                              as is_open,
    case when r.closed_date is not null
         then date_diff('day', r.created_date, r.closed_date) end as days_to_close,
    date_diff('day', r.created_date, current_date)       as age_days,
    r.planned_completion_days,
    r.latitude,
    r.longitude
from {{ ref('svc_requests') }} r
join {{ ref('dim_request_type') }} t
  on t.sr_type_desc = r.sr_type_desc and t.dept_name is not distinct from r.dept_name
