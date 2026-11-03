-- ODS and a CQC provider id may name the same organisation.
-- Any other mix of systems on one code is a collision.
select parent_code
from {{ ref('int_sites') }}
where parent_code is not null
group by parent_code
having count(distinct parent_code_system) > 1
    and bool_or(parent_code_system not in ('ods', 'cqc_provider'))
