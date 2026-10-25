select 1 as missing_merged_location
where (
    select count(*)
    from {{ ref('location') }}
    where source = 'ods+cqc'
        and nhs_code is not null
        and regulator = 'CQC'
        and regulator_id is not null
) = 0
