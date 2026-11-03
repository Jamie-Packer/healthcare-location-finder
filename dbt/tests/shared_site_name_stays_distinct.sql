{{ config(enabled=var('fixtures', false)) }}

select 'Example Shared Name' as name
where (
    select count(*)
    from {{ ref('location') }}
    where name = 'Example Shared Name'
) <> 2
or (
    select count(distinct location_id)
    from {{ ref('location') }}
    where name = 'Example Shared Name'
) <> 2
