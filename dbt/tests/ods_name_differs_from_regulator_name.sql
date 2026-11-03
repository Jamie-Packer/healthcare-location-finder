{{ config(enabled=var('fixtures', false)) }}

-- The site keeps the regulator's display name. The organisation-data name is a separate alias.
select 'RX9' as nhs_code
where (
    select count(*)
    from {{ ref('location') }} as location
    inner join {{ ref('entity_alias') }} as aliases
        on aliases.entity_id = 'site:' || location.location_id
        and aliases.alias_type = 'ods_name'
        and aliases.alias_text = 'EXAMPLE ODS WARD'
    where location.nhs_code = 'RX9'
        and location.name = 'Example Regulator Ward'
) <> 1
