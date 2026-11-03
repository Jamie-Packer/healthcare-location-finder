select provider_code
from {{ ref('int_providers') }}
group by provider_code
having count(*) > 1
