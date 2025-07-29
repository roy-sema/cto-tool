# Requirements for running full Anomaly Pipeline

A `.env` file in the root directory of this repository that contains:
- `ANTHROPIC_API_KEY`

Required Argument:

`--git_data_path`: Path to the Git data CSV file - ends with `_git_data_summary.csv`
`--git_repo_path`: Path of folder where git repositories are present

This will create a new column anomaly_summary and save in a new csv file, for every repository it will create 3 text file as output.
If we are running this again it will delete the previously created output files csv/texts generated with the same name and create new files.

# How to run fast onboarding pipeline

This pipelines creates a JSON file with anomalies out of the biggest repository from the provided folder.
More precisely, we use the repo that has the highest number of commits between `start-date` and `end-date` provided as parameters.

This pipeline should take about 20 seconds independently from the size of the repository and the analysis time window.

Example:
```
python main_fast_onboarding.py --git_repo_path <folder-with-different-repos> --start-date <e.g.-2024-02-01> --end-date <e.g.-2025-02-28> --output-path <output-path>
```

The location for the output JSON file will be shown in the last line printed out in stdout. E.g.:
```
Fast onboarding insights for repo ai_engine saved at <output-path>/<repo-name-with-max-commits>_anomaly_driven_insights.json
```
