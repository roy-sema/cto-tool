from typing import Annotated

from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.models.anomaly_insights import ConfidenceLevel, InsightCategory
from contextualization.tags import get_tags_prompt
from contextualization.tools.llm_tools import get_input_runnable
from contextualization.utils.output_parser import to_clean_dict_parser
from contextualization.utils.pydantic_validators import category_validator

system_template = """<task>
    {task}
    </task>
    Analyze the provided git diff to identify variances that reflect significant changes or anomalies in the engineering workflow. Specifically, focus on:
    Delivery Variance: Unusual timeline changes, scope modifications, resource adjustments, or priority shifts.
    Team Patterns: Significant workflow changes, collaboration shifts, or productivity anomalies. Summarize each commit’s variance as actionable insights, explaining its potential impact and whether it signals a positive, negative, or neutral deviation.
    f"Here's the diff: {diff_file}"
    "Please only return a single line of text without line breaks"
    "Your response will be written directly into a file so please do not include any commentary or formatting. Make sure your response is parsable line-by-line for each commit."    
"""


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["diff_file", "task"],
)

llm_diff_anomaly = get_llm(max_tokens=5000)
diff_anomaly_analyser_chain = prompt_template | llm_diff_anomaly

llm_diff_anomaly_big = get_llm(max_tokens=5000, big_text=True)
diff_anomaly_analyser_chain_big_text = get_input_runnable(big_text=True) | prompt_template | llm_diff_anomaly_big

#####################################################################################################
system_template_git_tree = """
Given a git tree created with git log --graph --oneline, create a high-level summary of patterns, delivery timeline, and anomalies relevant to leadership, focusing on system-level patterns rather than implementation details. The summary should include:

- Pattern Recognition: Identify recurring workflows, contribution rhythms, and development cycles based on commit and branch patterns
- Delivery Timeline Patterns: Map velocity patterns, release cadences, and milestone achievement trends from the commit history
- Collaboration Patterns: Highlight team dynamics and coordination approaches based on branch interaction patterns 
- Workflow Effectiveness: Evaluate the development process through patterns in integration frequency, branch management, and merge strategies

IMPORTANT - ACCURACY REQUIREMENTS:
1. First scan the ENTIRE git log to identify system-level patterns before making conclusions
2. Only extract and validate PR numbers and ticket numbers that EXACTLY match patterns like for pull request "#123" or "TICKET-456" in commit messages
3. Do not infer or create PR/ticket numbers that aren't explicitly mentioned
4. Verify each pattern observation with supporting evidence from different parts of the git log provided
5. For all identified anomalies and notable patterns, include the exact commit IDs from which they were observed
6. Never generate, infer, or fabricate commit IDs - only reference IDs explicitly present in the provided git log

For observed patterns, categorize insights into two categories:

# System Success Patterns (Priority):
- Key patterns that indicate positive system behaviors (consistent delivery cadence, efficient integration cycles, effective branching strategies)
- Evaluate for positive patterns in: release predictability, branch lifecycle management, integration smoothness, change propagation, and maintenance efficiency
- Focus on WHAT patterns emerged rather than HOW they were implemented
- Include specific commit IDs that exemplify each identified pattern

# System Risk Patterns:
- Divergent patterns that may impact system health (irregular delivery cadence, extended integration cycles, branch isolation)
- Evaluate for concerning patterns in: release unpredictability, branch management complexity, integration friction, change isolation, and maintenance burden
- Identify pattern shifts and variations rather than specific implementation issues
- Include specific commit IDs for each risk pattern to enable further investigation

Place any pattern observations that could indicate significant system changes under System Risk Patterns.

No implementation details or generic observations! Focus exclusively on observable system-level patterns backed by specific evidence from the git history.

Here is the git tree: {git_tree_content}"""

prompt_template_git_tree = PromptTemplate(
    template=system_template_git_tree,
    input_variables=["git_tree_content"],
)

llm_git_tree = get_llm(max_tokens=5000)
analyse_git_tree_chain = prompt_template_git_tree | llm_git_tree | StrOutputParser()

######################################################################################################
system_template_chunks = """

### **TAG DEFINITIONS**
{tag_definitions}

Given a batch of rows containing anomaly summaries, highlights generated from git commit diffs,  
Extract the recurring patterns, systemic trends, and notable deviations that may impact project success. Focus on identifying what changed (the pattern) rather than how it was implemented.
- **Do NOT include introductory text** such as "Here is the summary".  
- **Strictly follow the JSON schema** provided below.  

Prioritize positive highlights and achievements that demonstrate team success
### **JSON Structure:**  
1. **anomaly_insights**:  
   - A list of dictionaries, each containing:
     - "category": One of [ANOMALY_CATEGORIES]
     - "description": A clear statement of the observed pattern itself, focusing on what is happening at a system level rather than implementation specifics. Emphasize both positive patterns showing progress and negative patterns revealing challenges.
     - "evidence": Specific evidence showing the pattern's existence across multiple commits or components, demonstrating consistent behavior rather than isolated instances.
     - "significance_score": Assign the appropriate significance_score (1-10) based on the significance scale to prioritize findings
     - "confidence_level": Assign the appropriate confidence_level based on the confidence levels
     - "files": Include a list of file metadata where the patterns has been observed. Files is a list of dict with keys - "file_name", "branch_name", and "commit_id" and their respective values. Example of the files list is as follows:
     "files":[
        {{
            "commit_id" : "10b044b3",
            "file_name": "hotfix_1.py",
            "branch_name": "feature/release-june-15-2025"
        }},
        {{
            "commit_id" : "10c084z3",
            "file_name": "scans/url_contain.py",
            "branch_name": "origin/main"
        }},
     ]. 
     NEVER generate, infer, or fabricate the list of files. - only reference commit_id, file_name, and branch_name explicitly present in the provided data.
     Infer the value of the key file_name strictly as the full directory or relative path, including the file name and its extension (e.g., .txt, .csv, .py). Return the path exactly as it appears in the source data—do not guess, modify, or generate it. 
     
2. **risk_insights**:  
   - A list of dictionaries, each containing:
     - "category": One of [ANOMALY_CATEGORIES]
     - "description": A description of a recurring pattern that represents potential risk to project success, focusing on the systemic behavior rather than specific implementations.
     - "evidence": Specific evidence showing multiple instances of the pattern across different commits or components, demonstrating its pervasiveness.
     - "significance_score": Assign the appropriate significance_score (1-10) based on the significance scale to prioritize findings
     - "confidence_level": Assign the appropriate confidence_level based on the confidence levels
     - "files": Include a list of file metadata where the patterns has been observed. Files is a list of dict with keys - "file_name", "branch_name", and "commit_id" and their respective values. Example of the files list is as follows:
     "files":[
        {{
            "commit_id" : "10b044b3",
            "file_name": "hotfix_1.py",
            "branch_name": "feature/release-june-15-2025"
        }},
        {{
            "commit_id" : "10c084z3",
            "file_name": "scans/url_contain.py",
            "branch_name": "origin/main"
        }},
     ]. 
     NEVER generate, infer, or fabricate the list of files. - only reference commit_id, file_name, and branch_name explicitly present in the provided data.
     Infer the value of the key file_name strictly as the full directory or relative path, including the file name and its extension (e.g., .txt, .csv, .py). Return the path exactly as it appears in the source data—do not guess, modify, or generate it.

### **Category Definitions:**
[ANOMALY_CATEGORY_DEFINITIONS]

### **Significance Scale for significance_score:**
Levels 1-6: "Team Member's Attention"
    - Relevant to individual contributors or small sub-teams
    - Represents minor deviations (0-1σ) from baseline expectations
    - Limited to specific functions, features, or isolated components
    - Provides tactical information for day-to-day decision-making
Level 7: "Team Lead's Attention"
    - Relevant to daily operations of specific teams
    - Appropriate for team lead awareness
    - Represents moderate deviation (1-1.5σ) from baseline
    - Affects specific codebases or work patterns
    - Provides useful context for team-level decisions
Level 8: "Director/Manager's Attention"
    - Notable impact on specific product areas or technical components
    - Warrants director or senior manager attention
    - Represents significant deviation (such as 1.5-2σ) from baseline
    - Affects specific teams or product components
    - Provides important signals for technical decision-making
Level 9: "CTO/CPO's Attention"
    - Substantial impact on technical operations or delivery timelines
    - Requires attention from senior engineering or product leadership
    - Represents major deviation (such as 2-3σ) from expected patterns
    - Affects important systems or significant portion of development activity
    - Creates meaningful technical risk or opportunity
Level 10: "CEO's Attention"
    - Direct, measurable impact on business outcomes or major customer commitments
    - Requires organizational priority shift or immediate resource allocation
    - Represents significant deviation (such as >3σ but we may not calculate it as such) from normal operations
    - Affects multiple parts of the organization or critical system components
    - Creates material risk to revenue, security, or customer satisfaction
#### Scoring incorporates:
* Statistical deviation magnitude
* Business impact assessment
* Relation to critical path or strategic priorities
* Scope of impact (component, service, system-wide)

### **Security Risk Assessment Calibration:**
**For security-related anomalies, apply specialized significance scoring:**
- **Level 7-8 (Standard Security Operations)**: Individual vulnerability fixes, routine dependency updates, security code reviews, single security incidents, proactive security improvements
- **Level 9 (Critical Security Warnings)**: Security incidents with customer/data impact, multiple related security issues in short timeframe, external audit findings, emergency patching
- **Level 10 (Sustained Security Crisis)**: Pattern of critical security issues over 7+ days, active security incidents affecting production, systematic security failures, security issues requiring board notification

**Security Calibration Principles:**
- High CVSS scores alone don't warrant Level 9-10
- Individual security events = Level 7-8, regardless of technical severity  
- Clustered/sustained security patterns = Level 9-10
- Business impact and customer exposure drive higher levels
- Normal security hygiene is expected, not exceptional

### **Confidence Levels:**
- **High Confidence**: Strong statistical significance (p<0.01), large sample, consistent pattern
- **Medium Confidence**: Moderate significance (p<0.05), adequate sample, some variability
- **Low Confidence**: Borderline significance, limited data, or high variability

### **Rules for Output:**  
- Both `anomaly_insights` and `risk_insights` must be **lists** (even if empty).
- Each item MUST include "category", "description" and "evidence" fields with specific references from the commit data.
- **VERY IMPORTANT**: Do NOT classify routine development activities as patterns 
    - focus on:
        - Recurring behaviors that differ from expected development patterns
        - Systematic approaches that reveal organizational tendencies
        - Emergent directions that indicate shifts in project trajectory
- Only report true anomalies that indicate a fundamental misalignment with product goals or best practices.
- If no genuine anomalies or risks are detected, return empty lists.
- List the most critical/important insights first in each category.
- **Do not add extra fields**; the output must match the schema exactly.
### **Here's the data to analyze:**  
{chunk}
"""


class FileInfo(BaseModel):
    file_name: str
    branch_name: str
    commit_id: str


class InsightSchema(BaseModel):
    category: Annotated[InsightCategory, category_validator] = Field(description="The category of the insight")
    description: str = Field(description="Description about the insights. [FORMAT_AS_BULLET_POINTS]")
    evidence: str = Field(description="Evidence about the insights. [FORMAT_AS_BULLET_POINTS]")
    significance_score: float = Field(description="significance_score for each insight to indicate significance level")
    confidence_level: ConfidenceLevel = Field(description="Level of confidence in the anomaly")
    sources: list[str] = Field(description="List of accurate commit ids from provided input data for observed anomaly")
    files: list[FileInfo]


class ExecutiveSummary(BaseModel):
    anomaly_insights: list[InsightSchema] = Field(
        default_factory=list,
        description="A list of dictionaries, each containing 'category', 'description' and 'evidence' fields about a highlight, variance from previous practice.",
    )
    risk_insights: list[InsightSchema] = Field(
        default_factory=list,
        description="A list of dictionaries, each containing 'category', 'description' and 'evidence' fields about a negative variance from recommended practice.",
    )


prompt_template_chunks = PromptTemplate(
    template=system_template_chunks,
    input_variables=["chunk"],
    partial_variables={
        "tag_definitions": get_tags_prompt(format_as_bullet_points=True, include_anomaly_categories=True)
    },
)

llm_anomaly = get_llm(max_tokens=10_000).with_structured_output(ExecutiveSummary) | to_clean_dict_parser
analyse_chunks_chain = prompt_template_chunks | llm_anomaly


##############################################################################

system_template_anomaly = """
You are an expert in analyzing critical anomalies in software development and infrastructure. 

Given a list of anomalies from different repositories, rank them in order of importance based on the severity of the issue, potential security impact, risk to system stability, and business-critical consequences. 

A revert due to a major failure is more severe than minor cleanup commits. Security vulnerabilities should be prioritized over performance optimizations. Infrastructure instability should be prioritized over code style issues.

### Input Format:
A list of objects where each object contains:
- "repo": Repository name
- "critical_anomaly": Description of the issue

### Task:
1. Analyze the anomalies and rank them from most to least critical.
2. Maintain the same structure in the output, but reorder the list based on critical priority.

Here is the data:{analysis_content}

### Output Format:
- **Do NOT include introductory text** such as "Here is the ranked JSON".
"""


class Anomaly(BaseModel):
    repo: str
    critical_anomaly: str
    evidence: str


class RankedAnomalies(BaseModel):
    critical_anomalies: list[Anomaly]


prompt_template_summary = PromptTemplate(
    template=system_template_anomaly,
    input_variables=["analysis_content"],
)

llm_ranking = get_llm(max_tokens=15_000).with_structured_output(RankedAnomalies) | to_clean_dict_parser
anomaly_ranking_chain = prompt_template_summary | llm_ranking

#####################################################################################################

system_template_skip_a_meeting = """

### **TAG DEFINITIONS**
{tag_definitions}

### **Category Definitions:**
[ANOMALY_CATEGORY_DEFINITIONS]

You are an expert in analyzing critical anomalies in software development and infrastructure. For context, these anomalies are extracted by analyzing the Git tree and the code changes being pushed into Git. The analysis considers both the structural changes in the repository and the modifications within the code to identify risks.
Given the following anomaly details:
### Input Format:
A dictionary where the keys are constant and the value is explanation of of the keys in this example:
    "repo": "Name of the repository",
    "category": "Category of the anomaly (e.g., [ANOMALY_CATEGORIES]),
    "insight": "Insights about the anomaly, what is the anomaly and its description",
    "evidence": "Where the anomaly is present or where in the code/file/function we can see that anomaly",
    "significance_score": "A Score based on significance of the anomaly ,
    "confidence_level": "A confidence level based on significance score (i.e., High,Medium,Low)"
#significance_score scale information:
    Level 10: CEO's Attention (Executive leadership)
    Level 9: CTO/CPO's Attention (Technical/Product leadership)
    Level 8: Director/Manager's Attention (Department heads)
    Level 7: Team Lead's Attention (Technical team leaders)
    Levels 1-6: Team Member's Attention (Developers, QA, individual contributors)
### Task:
- Given the following insight, your task is to generate a SkipAMeeting suggestion. This should include:
- How the issue can be resolved asynchronously (e.g., providing documentation links, steps to fix).
- Dynamic audience determination: As significance score decide the sender of message. Determine multiple relevant audience types that should receive communications.
- Multiple audience-specific messages, where each message is tailored to a specific stakeholder group.
    A message should:
        - Frame the issue as an opportunity for collaborative problem-solving in short
        - Present thought-provoking questions that prompt specific, substantive responses
        - Suggest relevant context that enables asynchronous discussion

{analysis_content}
Instructions:
- Maintain tone between -2 and +2 on a -10 to +10 emotional scale.
- Use moderate language: Maximum positive: "pleased" (never "excited," "thrilled"); Maximum negative: "unfortunately" (never "alarming," "critical").
- Avoid first-person references ("I," "we," "our").
- Use objective, third-person descriptions focused on data and events rather than opinions.
- Attribute observations to systems/data rather than people.
- Convey urgency through impact statements and precise metrics rather than emotional language.
- Replace imperative commands with options (e.g., "Implementation options include..." instead of "Please implement...").
- Be clear and direct—avoid unnecessary details.
- Ensure the message is actionable so that teams can quickly address the issue.
- Use the insight details to craft a relevant and effective response.
- Provide specific steps or solutions, not vague suggestions.
- Based on the significance score, determine the appropriate audience and tailor your message accordingly.

Instructions for "resolution":
    For negative anomalies:
        - Provide 2-3 specific, actionable steps to address the issue
        - Include potential technical approaches with their respective trade-offs
        - Reference relevant documentation, best practices, or similar past incidents if applicable
        - Suggest testing or validation methods to confirm resolution
        - Indicate priority level based on significance score and business impact
    For positive anomalies:
        - Summarize the beneficial aspects and potential value to the organization
        - Suggest ways to leverage or expand upon the positive development
        - Identify opportunities for knowledge sharing or standardization
        - For higher significance scores (7-10), include potential strategic implications
        - For lower significance scores (1-6), focus on tactical implementation details
    You may also include when needed:
        - Scale technical complexity according to the target audience
        - Include estimated effort/time investment when relevant
        - Suggest appropriate documentation updates or knowledge sharing actions
        - Provide clear success criteria that indicate when the matter is resolved
        - Number the steps in the resolution for clarity
        - Always add a new line after each step

Instructions for "message":
- Focus on generating 2-3 specific, non-obvious questions that require thoughtful responses.
- Provide enough context for informed discussion without prescribing complete solutions.
- Include clear indicators of what type of feedback would be most valuable.
- Ensure questions are specific to the anomaly details and cannot be answered with yes/no.
- Structure messages to invite ongoing conversation rather than close discussion.
- May include a question that talk about the approaches when needed
- Adapt message complexity and technical detail based on the audience determined by the significance score.
- For positive anomalies, frame questions around optimization and strategic leverage
- For negative anomalies, frame questions around risk mitigation and technical solutions
- **IMPORTANT** Do not include names of developer or team members.


### Output Format:
- **Do NOT include introductory text** such as "Here is the description,etc".
"""


class Audience(BaseModel):
    audience: str = Field(description="Who (person/team) should solve this")
    message_for_audience: str = Field(description="Specific message based on the audience. [FORMAT_AS_BULLET_POINTS]")


class SkipAMeeting(BaseModel):
    resolution: str = Field(
        description="insights to skip the meeting based on anomaly and how to resolve this issue asynchronously"
    )
    messages: list[Audience] = Field(description="Based on the audience, provide the specific message")


prompt_template_skip_a_meeting = PromptTemplate(
    template=system_template_skip_a_meeting,
    input_variables=["analysis_content"],
    partial_variables={
        "tag_definitions": get_tags_prompt(format_as_bullet_points=True, include_anomaly_categories=True)
    },
)

llm_skip_a_meeting = get_llm(max_tokens=5_000).with_structured_output(SkipAMeeting) | to_clean_dict_parser
skip_a_meeting_chain = prompt_template_skip_a_meeting | llm_skip_a_meeting


###############################################################################################################################

system_template_blind_spot = """
Analyze the provided risk and anomaly insights and identify similar patterns elsewhere in the codebase. 

For each insight provided, you must identify "Blind Spots" - other instances of the same type of problem or pattern.

A Blind Spot analysis should find:
- **Problems found in location X but not fixed**: Identify other locations Y, Z with the same issue
- **Problems found in location X and already fixed**: Identify other locations Y, Z that could benefit from the same solution

### Instructions:
1. **Analyze each insight individually** to understand the core pattern/problem
2. **Search conceptually** for similar patterns that would exist elsewhere in a typical codebase
3. **Provide specific location descriptions** when possible (file types, component areas, function patterns)
4. **Create actionable resolutions** that address both the original and newly identified instances
5. **Be realistic** - if no additional instances would logically exist, state so clearly

### Output Requirements:
- Add a "blind_spot" field to each insight containing:
  - "location": Where similar patterns are found (or "No additional instances found beyond those mentioned in the evidence")
  - "resolution": Consolidated approach to fix all instances

### Format Rules:
- **Do NOT include introductory text** such as "Here is the analysis"
- **Return only valid JSON** matching the input structure with blind_spot fields added
- **Preserve all original fields** exactly as provided
- **Focus on actionable information** with minimal repetition

### Input Insight:
{insight}
"""


class BlindSpot(BaseModel):
    location: str = Field(
        description="Description of where similar patterns are found in the codebase, or 'No additional instances found beyond those mentioned in the evidence' if none exist"
    )
    resolution: str = Field(
        description="Consolidated resolution approach addressing the original issue and all similar instances efficiently"
    )


class AnomalyWithBlindSpot(BaseModel):
    blind_spot: BlindSpot = Field(description="Blind spot analysis for similar patterns")


prompt_template_blind_spot = PromptTemplate(
    template=system_template_blind_spot,
    input_variables=["insight"],
)

llm_blind_spot = get_llm(max_tokens=5000).with_structured_output(AnomalyWithBlindSpot) | to_clean_dict_parser
blind_spot_chain = prompt_template_blind_spot | llm_blind_spot
