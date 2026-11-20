{{ config(enabled=var('fixtures', false)) }}

select 'RX3' as code
where (
    select count(*)
    from {{ ref('location') }}
    where nhs_code = 'RX3'
        and regulator_id = 'RX3'
        and source = 'ods+cqc'
) <> 1
   or (
    select count(*)
    from {{ ref('location') }}
    where nhs_code = 'RX3' or regulator_id = 'RX3'
) <> 1
