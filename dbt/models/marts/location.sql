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
                ods_name,
                brand_name,
                parent_name,
                town,
                postcode,
                postcode_compact,
                ods_code,
                cqc_location_id
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
                token -> token <> ''
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
    postcode,
    postcode_compact,
    town,
    local_authority_name,
    local_authority_code,
    county_name,
    county_code,
    region_name,
    region_code,
    icb_name,
    icb_code,
    icb_ods_code,
    country_name,
    ods_code,
    cqc_location_id,
    service_type,
    valid_from,
    valid_to,
    match_string
from cleaned
