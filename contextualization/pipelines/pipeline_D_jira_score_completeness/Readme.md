## Running the Pipeline D: JIRA Completeness Score

Execute the following command to run the pipeline:

Run the Pipeline Using Pre-Fetched Jira Data (--jira_data_path):
If you already have Jira data from Pipeline B and C ends with `jira_data_with_git_initiatives.csv`, use this:

```bash
python3 jira_completeness_score.py --jira_data_path "path/to/jira_data_with_git_initiatives.csv" --output_path "jira_complete_score_output" 
```

If you don't have Jira data file, use this:

```bash
python3 jira_completeness_score.py --jira_url "https://semalab.atlassian.net" --confluence_user "your-confluence-user-id" --confluence_token "your-confluence-token" --start_date YYYY-MM-DD --end_date YYYY-MM-DD --output_path "jira_complete_score_output" --jira_projects jira-project
```
Note: Here --jira-projects can be CON and make sure you create the output_folderand provide its path.

If you connect through Jira APIs, run the following:
```bash
python3 jira_completeness_score.py --jira_url "https://semalab.atlassian.net" --jira_access_token "jira_access_token_from_APIs" --start_date YYYY-MM-DD --end_date YYYY-MM-DD --output_path "jira_complete_score_output" --jira_projects jira-project
```
