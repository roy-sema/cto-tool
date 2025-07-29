# Sema GenAI Detector

{% if not pull_request.analysis_num_files %}
None of the files changed in this PR are supported by the Sema GenAI Detector.
{% else %}
{% if pull_request_pass %}🎉{% elif not pull_request_pass %}🚨{% else %}⚠️{% endif %} {{ message }}
{% endif %}

[More Details]({{ details_url }})

Evaluated on: {{ pull_request.updated_at }} UTC
Commit SHA: `{{ pull_request.head_commit_sha }}`

{% if pull_request.analysis_num_files %}
## GenAI Composition for this PR
{% include "markdown/ai-summary.md" with ai_composition=ai_composition pr=True analyzed_files=pull_request.analysis_num_files not_evaluated_files=pull_request.not_evaluated_num_files rules=rules only %}

## Legend

🟢 - strength
🟡 - low risk
🟠 - medium risk
🔴 - high risk
⚪ - no strength / not apply
{% endif %}
