-- Warn if more than 5% of requests are being quarantined: that usually means the
-- source changed shape, not that 5% of the city's requests are bad.
{{ config(severity='warn') }}
select count(*) filter (where dq_reason is not null) * 1.0 / count(*) as share
from {{ ref('svc_requests_checked') }}
having share > 0.05
