{% test unique_combination(model, combination) %}
select
    {% for column in combination %}
    {{ column }}{% if not loop.last %},{% endif %}
    {% endfor %},
    count(*) as rows
from {{ model }}
group by all
having count(*) > 1
{% endtest %}
