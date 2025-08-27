from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field, conint

from contextualization.conf.get_llm import get_llm
from contextualization.pipelines.pipeline_A_automated_process.evals.prompt_chatgpt import (
    diff_analyser_chain as prompt_chatgpt,
)
from contextualization.pipelines.pipeline_A_automated_process.evals.prompt_claude import (
    diff_analyser_chain as prompt_claude,
)

system_prompt_template = """
# System (role)
You are a meticulous evaluation judge. You only use the provided task description, inputs, and candidate responses. 
Do not use external knowledge. Be strict, consistent, reproducible, and deterministic.

# Rubric (weights sum to 100)
- Groundedness & Correctness (30): Stays within given inputs; no hallucinations or contradictions.
- Coverage & Relevance (20): Addresses all required sections/aspects of the task; avoids fluff.
- Task Format Compliance (20): Follows the task’s requested structure (e.g., required headings/sections/enums/word caps).
- Specificity & Evidence (10): Cites concrete paths/functions/line ranges from inputs when present.
- Reasoning Quality (10): Clear logic; identifies risks/edge cases; sound justification.
- Conciseness (5): Efficient wording; respects any word limits.
- Safety/Constraints (5): Honors guardrails (e.g., closed category enum; no invented tech).

# Tie-breaks (apply in order)
- Higher Groundedness & Correctness
- Higher Specificity & Evidence
- Higher Conciseness

# Inputs
- Source inputs: {prompt_one_response} {prompt_two_response}

# Evaluation procedure
1) Read the task specification and note the mandatory structure, enums, and limits.
2) Read the source inputs; treat them as the only facts allowed.
3) For each candidate, judge strictly against the rubric:
   - Verify adherence to the task’s required structure and constraints.
   - Penalize unsupported claims, invented repositories/files/technologies, and missing required sections.
   - Assign integer scores per dimension; compute a total score (0–100).
   - Record 1–3 concise violations or highlights (e.g., “non-enum category used: Performance”, “invented file not in diff”).
4) After scoring all candidates, rank them by total score; resolve ties using the tie-break rules.
5) Provide the winner id.

# Judge rules
- Do not rewrite, repair, or validate candidates; judge them as-is.
- Be consistent across candidates; use the same thresholds for scoring.
- If candidates breach closed enums or required sections, penalize Task Format Compliance; also penalize Groundedness if claims exceed inputs.
- Keep notes minimal, concrete, and focused on decisive issues.

"""


class Scores(BaseModel):
    prompt_one_total_score: int = conint(ge=0, le=100)
    prompt_two_total_score: int = conint(ge=0, le=100)
    summary: str
    reasoning: str
    prompt_to_chose: str = Field(description="Write prompt_one or prompt_two, which should be chosen to go further")


prompt_template = PromptTemplate(
    template=system_prompt_template,
    input_variables=["prompt_one_response", "prompt_two_response"],
)

llm = get_llm(max_tokens=5_000).with_structured_output(Scores)
prompt_results_evaluation = prompt_template | llm


diff = """<input diff>"""
commit_description = """<input_commit_description>"""
tittle_description = """<input_commit_tittle>"""

claude_response = prompt_claude.invoke({"diff": diff, "title": tittle_description, "description": commit_description})
chatgpt_response = prompt_chatgpt.invoke({"diff": diff, "title": tittle_description, "description": commit_description})


evaluation_score = prompt_results_evaluation.invoke(
    {
        "prompt_one_response": claude_response.model_dump(),
        "prompt_two_response": chatgpt_response.model_dump(),
    }
)
