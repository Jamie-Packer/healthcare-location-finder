select 1 as missing_merged_location
where (
    select count(*)
    from {{ ref('location') }}
    where ods_code is not null
        and cqc_location_id is not null
) = 0
