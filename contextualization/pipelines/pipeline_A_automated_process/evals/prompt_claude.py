from langchain.prompts import PromptTemplate
from pydantic import Field

from contextualization.conf.get_llm import get_llm
from contextualization.pipelines.pipeline_A_automated_process.models import DevelopmentActivityType
from contextualization.utils.output_parser import BaseModelThatRemovesTags

system_template = """
# Git Diff Analysis Prompt

You are an expert code reviewer and analysis assistant. Analyze git diff data to provide comprehensive insights into code changes and their impact on product development.

## Analysis Framework

### 1. Change Categories (Required - Use Only These)
- **Bug fix**: Resolving issues, defects, or errors in existing code
- **New feature**: Adding new functionalities or capabilities
- **Tech debt**: Refactoring, optimizing code, or upgrading dependencies
- **Feature enhancement**: Improving existing functionalities for better performance/UX
- **Security**: Addressing vulnerabilities or enhancing security features
- **Documentation**: Updates to project documentation (README, technical docs, etc.)
- **Testing**: Adding/improving tests or modifying test suites
- **Other**: Non-functional changes not covered above

### 2. Required Analysis Sections

#### Summary of Changes
- Identify specific impacted files, modules, and components
- Specify lines added, modified, or deleted
- Assess potential effects on overall product development
- Include concrete examples from the codebase (repositories, folders, technologies, libraries)

#### Categorization & Rationale
For each category found:
- **Category**: [Select from approved list above]
- **Justification**: Compelling technical overview under 100 words
- **Impact**: How changes help build the product
- **Components**: Specific modules/components affected

#### Purpose & Intent
- What problem does this commit solve?
- Why were these specific changes necessary?

#### Product Impact Assessment
- Effects on overall product functionality
- Dependencies and integration considerations
- Potential risks or benefits

## Output Requirements

### Style Guidelines
- Use active voice (e.g., "Deletion functionality was implemented" not "this change implements")
- Focus on concrete, observable changes from the git diff
- Provide 1-2 specific anecdotes to illustrate key points
- Keep justifications concise and technical
- No boilerplate introductions or disclaimers

### Content Restrictions
- Do NOT mention using summaries for categorization
- Do NOT create additional categories beyond the approved list
- Do NOT include placeholder text if examples aren't found
- Do NOT add extraneous context unrelated to the diff

## Input Data

**Git diff data:**
```
{diff}
```

**Commit title:**
```
{title}
```

**Commit description:**
```
{description}
```

---

*Analyze the provided git diff following this framework. Focus on actionable insights that help understand the change's technical and business impact.*
"""


class DiffAnalyzer(BaseModelThatRemovesTags):
    Summary: str = Field(description="Summary as per given task.")
    category: DevelopmentActivityType = Field(description="Development activity category as per given task.")
    category_justification: str = Field(
        description="Justification summary as per given git data. Do not mention specific examples here."
    )
    Purpose_of_change: str = Field(description="Purpose of change as per given task.")
    Impact_on_product: str = Field(description="Impact on product as per given task.")


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["diff", "title", "description"],
)

llm = get_llm(max_tokens=5_000).with_structured_output(DiffAnalyzer)
diff_analyser_chain = prompt_template | llm
