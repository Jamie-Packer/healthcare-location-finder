{% snapshot snap_location %}

{{
    config(
        target_schema='main',
        unique_key='location_id',
        strategy='check',
        check_cols=['name', 'parent_name', 'postcode', 'nhs_code', 'service_type', 'regulator_id', 'country_name', 'health_area_code'],
        hard_deletes='invalidate'
    )
}}

select
    location_id,
    name,
    parent_name,
    postcode,
    nhs_code as ods_code,
    nhs_code,
    service_type,
    regulator_id,
    country_name,
    health_area_code
from {{ ref('location') }}

{% endsnapshot %}
