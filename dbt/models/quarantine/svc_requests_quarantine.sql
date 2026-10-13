-- Requests held back for review, with the rule they broke.
select
    sr_number, sr_type_desc, created_date, closed_date, latitude, longitude,
    dq_reason, _ingested_at as first_seen_at
from {{ ref('svc_requests_checked') }}
where dq_reason is not null
