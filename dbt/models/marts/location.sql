{% set stopwords = [
    'A', 'AN', 'AND', 'AT', 'FOR', 'IN', 'OF', 'ON', 'THE', 'TO',
    'NHS', 'TRUST', 'FOUNDATION',
    'HOSPITAL', 'HOSPITALS',
    'CENTRE', 'CENTER', 'CLINIC', 'CLINICS',
    'LIMITED', 'LTD', 'PLC',
    'ROAD', 'STREET', 'AVENUE', 'LANE', 'DRIVE', 'CLOSE', 'WAY', 'COURT', 'PLACE'
] %}

with sites as (
    select
        *,
        trim(regexp_replace(
            upper(concat_ws(
                ' ',
                name,
                alt_name,
                brand_name,
                parent_name,
                town,
                postcode,
                postcode_compact,
                nhs_code,
                regulator_id
            )),
            '[^A-Z0-9]+',
            ' ',
            'g'
        )) as match_tokens
    from {{ ref('int_sites') }}
),

cleaned as (
    select
        * exclude (match_tokens),
        trim(array_to_string(
            list_filter(
                string_split(match_tokens, ' '),
                lambda token: token <> ''
                    and token not in (
                        {% for word in stopwords %}
                        '{{ word }}'{% if not loop.last %}, {% endif %}
                        {% endfor %}
                    )
            ),
            ' '
        )) as match_string
    from sites
)

select
    location_id,
    name,
    parent_name,
    parent_code,
    address,
    postcode,
    postcode_compact,
    town,
    local_authority_name,
    local_authority_code,
    county_name,
    county_code,
    region_name,
    region_code,
    health_area_name,
    health_area_code,
    health_area_ods_code,
    health_area_type,
    country_name,
    nhs_code,
    regulator,
    regulator_id,
    service_type,
    source,
    valid_from,
    valid_to,
    match_string
from cleaned
