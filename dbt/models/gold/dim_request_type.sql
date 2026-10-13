-- One row per 311 request type, rolled up into a handful of plain-language categories.
select
    md5(sr_type_desc || '|' || coalesce(dept_name, '')) as request_type_key,
    sr_type_desc,
    dept_name,
    any_value(dept_division) as dept_division,
    case
        when regexp_matches(sr_type_desc, 'TRASH|BULK|YARD WASTE|RECYCL|CORNER CAN|COLLECT|CART|METAL FURNITURE|TIRE') then 'Trash and recycling'
        when regexp_matches(sr_type_desc, 'POTHOLE|STREET|SIDEWALK|SIGN|SIGNAL|LIGHT|PAVEMENT|CURB|ALLEY|BRIDGE') then 'Streets and traffic'
        when regexp_matches(sr_type_desc, 'DUMPING|GRAFFITI|LITTER') then 'Dumping, graffiti and litter'
        when regexp_matches(sr_type_desc, 'GRASS|WEED|BUILDING|VACANT|PROPERTY|HOUSING|NUISANCE|ZONING') then 'Buildings and property'
        when regexp_matches(sr_type_desc, 'VEHICLE|PARK|ABANDON') then 'Vehicles and parking'
        when regexp_matches(sr_type_desc, 'TREE|PARK|RECREATION') then 'Trees and parks'
        when regexp_matches(sr_type_desc, 'WATER|SEWER|DRAIN|SMU') then 'Water and sewer'
        else 'Other'
    end as category
from {{ ref('svc_requests') }}
group by sr_type_desc, dept_name
