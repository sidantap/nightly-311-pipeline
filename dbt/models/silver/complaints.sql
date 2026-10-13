-- One row per NHTSA complaint. A complaint with exactly one known component gets a
-- clean label (component_group) for training and scoring the classifier.
with rows_latest as (
    select * from {{ ref('stg_nhtsa') }}
    qualify row_number() over (partition by complaint_id, component order by _ingested_at desc) = 1
),
per_complaint as (
    select
        complaint_id,
        any_value(make)          as make,
        any_value(model)         as model,
        any_value(model_year)    as model_year,
        bool_or(crash)           as crash,
        bool_or(fire)            as fire,
        max(injured)             as injured,
        max(deaths)              as deaths,
        any_value(state)         as state,
        min(received_date)       as received_date,
        min(added_date)          as added_date,
        any_value(description)   as description,
        count(*)                 as n_components,
        string_agg(component, ' | ' order by component) as components,
        any_value(component_prefix) as component_prefix
    from rows_latest
    group by complaint_id
)
select
    p.* exclude (component_prefix),
    case when p.n_components = 1 then g.component_group end as component_group
from per_complaint p
left join {{ ref('component_groups') }} g on g.component_prefix = p.component_prefix
where length(p.description) >= 40
