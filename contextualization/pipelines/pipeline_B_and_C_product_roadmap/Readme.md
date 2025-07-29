# Requirements for Pipeline B

A `.env` file in the root directory of this repository that contains:
- `ANTHROPIC_API_KEY`

Required Argument:

`--git_data_path`: Path to the Git data CSV file - ends with `_git_data_summary.csv`

This will run Pipeline B only on Git data.

# Use Jira input

Run as follows to use Jira as well as Git as input:
```
python main.py --git_data_path <--file-name--git_data_summary.csv> --confluence_user <jira-user-name> --confluence_token <jira-token> --jira_url <url-e.g.-https://semalab.atlassian.net> --jira_projects <PROJ1 PROJ2 PROJ3> --jira_start_date <e.g., 2024-05-01> --jira_end_date <e.g., 2024-05-31>
```

## Debugging Jira

Pass the parameter `--jira_data_path` if you want to use a manual CSV export from Jira. This overrides the call to Jira API.

# Chat

## Chat for Git initiatives

Pass the parameter `--chat_input` to modify the analysis

## Chat for Jira initiatives

TODO
