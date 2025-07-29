# JIRA Anomaly Analysis Pipeline

This pipeline analyzes JIRA tickets to identify anomalies and potential risks, providing detailed insights to help teams improve their ticket management and project oversight.

## Overview

The JIRA Anomaly Analysis Pipeline examines JIRA ticket data to detect:
- Anomalies in ticket creation, updates, and workflows
- Potential project risks based on ticket patterns
- Quality and completeness issues across projects

The pipeline processes tickets by project, generates batch analysis, and provides both detailed insights and executive summaries to support data-driven decision making.

## Folder Structure

```
pipeline_jira_anomaly_analysis/
├── output/
│   ├── PROJECT_anomaly_insight.json
│   ├── PROJECT_summary_jira_anomalies.json
│   ├── PROJECT_anomaly_analysis_error.csv
│   └── all_projects_summary.json
├── prompts/
│   ├── jira_anomaly_prompt.py
└── jira_anomaly_analysis.py
```

## Running the Pipeline

Run `pipeline_D_jira_score_completeness`.
Use following command 

```bash
python3 jira_completeness_score.py --jira_url "https://semalab.atlassian.net" --jira_access_token "jira_access_token_from_APIs" --start_date YYYY-MM-DD --end_date YYYY-MM-DD --output_path "jira_complete_score_output" --jira_projects jira-project
```
Output file `jira_data_with_score.csv` will be the input file for Jira Anomaly Insights. 


Execute the following command to run this pipeline:

```bash
python3 jira_anomaly_analysis.py --input_path "/path/to/jira_data_with_score.csv" --output_path "/path/to/output_directory"
```

The final output for this pipeline will be `jira_all_projects_skip_meeting.json` in the output path.

## Key Components

### 1. Required Input Data

The pipeline requires a CSV file with the following columns:
- `issue_key`: Unique identifier for the JIRA ticket
- `changelog`: History of changes to the ticket
- `summary`: Brief description of the ticket
- `Issue Type`: Type of the JIRA issue (Bug, Story, etc.)
- `created`: Creation timestamp
- `description`: Detailed ticket description
- `priority`: Ticket priority level
- `labels`: Associated labels
- `assignee`: Person assigned to the ticket
- `updated`: Last update timestamp
- `status`: Current ticket status
- `jira_completeness_score`: Quality score from the completeness pipeline
- `explanation_jira_completeness_score`: Explanation of the completeness score

### 2. Main Script

- **jira_anomaly_analysis.py**: The main script that orchestrates the entire pipeline, from data loading to insight generation and summary.

### 3. Key Functions

- **validate_dataframe()**: Ensures input data has all required columns
- **extract_project_from_issue_key()**: Parses project identifier from issue keys
- **format_df_for_llm()**: Prepares data for language model processing
- **analyze_batch_with_token_callback()**: Processes batches with token tracking
- **summarize_project_insights()**: Creates project-level summaries
- **process_project_data()**: Handles all processing for a specific project

### 4. Output Files

- **PROJECT_anomaly_insight.json**: Contains detailed anomaly and risk insights for each project
- **PROJECT_summary_jira_anomalies.json**: Provides summarized insights for each project
- **all_projects_summary.json**: Combines summaries across all projects
- **all_projects_skip_meeting.json**: Anomalies with skip a meeting added
- **PROJECT_anomaly_analysis_error.csv**: Logs any errors encountered during processing

## Processing Methodology

The pipeline follows these key steps:

1. **Data Validation and Preparation**
   - Validates input data format
   - Groups tickets by project
   - Calculates token counts for optimal batch sizing

2. **Batch Processing**
   - Splits project data into manageable batches
   - Processes each batch with rate limit awareness
   - Tracks token usage for efficiency monitoring

3. **Anomaly and Risk Detection**
   - Identifies patterns that deviate from normal ticket flows
   - Detects potential project risks based on ticket characteristics
   - Evaluates process adherence and workflow efficiency

4. **Insight Summarization**
   - Aggregates insights across all batches for each project
   - Generates executive summaries with key findings
   - Provides actionable recommendations based on identified issues

## Error Handling

The pipeline includes robust error handling for:
- Rate limit exceeded errors (exits gracefully to avoid account lockout)
- Timeout errors (skips problematic batches)
- Processing exceptions (logs details for debugging)
- Missing columns or data format issues

Errors are logged to separate CSV files with the suffix `_error.csv`

## Dependencies

This pipeline requires the following key libraries:
- pandas
- langchain_community
- tiktoken
- timeout_decorator

Additional imports from the project's internal modules:
- conf.config
- pipelines.pipeline_B_and_C_project_information.main
- pipelines.pipeline_A_automated_process.task1
- prompts.jira_anomaly_prompt
