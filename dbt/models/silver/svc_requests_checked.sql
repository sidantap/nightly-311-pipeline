-- Latest version of each request, with a data quality verdict.
-- Rows that fail a rule are routed to quarantine instead of being dropped or passed through.
with latest as (
    select *
    from {{ ref('stg_311') }}
    qualify row_number() over (
        partition by sr_number
        order by last_updated_at desc nulls last, _ingested_at desc
    ) = 1
)
select
    l.*,
    coalesce(s.status_group, 'unknown') as status_group,
    case
        when l.sr_number is null                             then 'missing_id'
        when l.created_date is null                          then 'missing_created_date'
        when l.closed_date < l.created_date                  then 'closed_before_created'
        when l.created_date > current_date                   then 'created_in_future'
        when l.latitude is null or l.longitude is null       then 'missing_location'
        when l.latitude  not between 38.9 and 39.4
          or l.longitude not between -84.9 and -84.2         then 'location_outside_city'
    end as dq_reason
from latest l
left join {{ ref('status_groups') }} s using (sr_status)
