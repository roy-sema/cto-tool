# Requirements for running aggregate git anomaly insights

A `.env` file in the root directory of this repository that contains:
- `ANTHROPIC_API_KEY`

Required Argument:

`--input_file`: Path to the final Git anomaly JSON file - `combined_anomaly_driven_insights.json`


# How to run aggregate git anomaly pipeline

To get the `combined_anomaly_driven_insights.json` file, run `anomaly_driven_insights` pipeline as:

```bash
python main.py --git_data_path "git_data_summary.csv file path" --git_repo_path "Folder containing repositories"
```
Then run aggregate git anomaly pipeline:

```bash
python main.py --input_files "git_anomaly_file" "jira_anomaly_file" --output_folder "output_folder_path(Optional)" --logging_file "Optional"
```
