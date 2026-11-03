select parent_code, source
from {{ ref('int_sites') }}
where parent_code_system = 'unknown'
