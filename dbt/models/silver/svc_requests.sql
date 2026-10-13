-- Requests that passed every data quality rule.
select * exclude (dq_reason)
from {{ ref('svc_requests_checked') }}
where dq_reason is null
