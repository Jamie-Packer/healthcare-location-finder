{{ config(severity='warn') }}

-- Wales, Scotland and Northern Ireland are not merged across sources, so one
-- place can come from two registers.
select upper(name) as name, postcode_compact, list(distinct source) as sources
from {{ ref('location') }}
where country_name <> 'England'
    and name is not null
    and postcode_compact is not null
group by 1, 2
having count(distinct source) > 1
