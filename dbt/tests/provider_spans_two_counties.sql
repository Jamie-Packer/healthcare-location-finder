{{ config(enabled=var('fixtures', false)) }}

select 'RXX' as parent_code
where (
    select count(*)
    from {{ ref('location') }}
    where parent_code = 'RXX'
) = 0
or (
    select count(distinct county_name)
    from {{ ref('location') }}
    where parent_code = 'RXX'
) < 2
