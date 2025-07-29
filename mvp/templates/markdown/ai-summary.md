{% load custom_filters %}
{% include "markdown/ai-table-header.md" with ai_composition=ai_composition only %}{% nolinebreaks %}
{% for ai_type in ai_composition %}
| {% include "markdown/color-emoji.md" with color=ai_type.color only %} {{ ai_type.value }}%
{% endfor %}
{% endnolinebreaks %}

{% if pr %}
Analyzed: {{ analyzed_files }} files · Not evaluated: {{ not_evaluated_files }} files
{% elif evaluated_percentage %}
{{ evaluated_percentage }}% of code evaluated
{% endif %}
{% if rules %}
**RULES**

{% include "markdown/ai-table-header.md" with ai_composition=ai_composition only %}{% for ai_type_rules in rules %}{% nolinebreaks %}
{% for rule, color in ai_type_rules %}
| {% if rule %}{% include "markdown/color-emoji.md" with color=color only %} {{ rule.name }}
{% endif %}
{% endfor %}

{% endnolinebreaks %}
{% endfor %}
{% endif %}
