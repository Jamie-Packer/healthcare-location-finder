{{ config(enabled=var('fixtures', false)) }}

select 'RX4' as code
where (
    select count(*)
    from {{ ref('location') }}
    where nhs_code = 'RX4' or regulator_id = 'RX4'
) <> 2
