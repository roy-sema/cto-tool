# Requirements for automated analysis

A `.env` file in the root directory of this repository that contains:
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `LLM` the LLM you want to use. See `conf/config.yaml` for the possible options under `llms`.

Also, if you want to use AWS Bedrock models you have to set up credentials with permissions for AWS Bedrock.

# How to run

Run `main.py`.

If you want to add groupings run as `ubuntu` on a production machine:
```
export ORG_NAME="<ORG-NAME>" ; psql postgresql://$DBUSER:$DBPASSWORD@$PRODDBHOST/$PRODDBNAME -c "\COPY (SELECT org.name org_name, proj.name proj_name, rg.* FROM public.organizations org JOIN public.projects proj on org.id = proj.organization_id JOIN public.repo_groupings rg ON proj.id = rg.repo_id WHERE org.name = '$ORG_NAME') TO '${ORG_NAME}_output.csv' WITH CSV HEADER;"
```

Then, a possible way to run `main.py` is:
```
python main.py --git-folder-path /home/ubuntu/customer-source-nfs-production/customer-source/<org-name> --start-date 2024-XX-XXT00:00:00 --end-date 2024-XX-XXT23:59:59 --output-path <output-path> --csv-grouping-file <csv-from-the-previous-query> --logging-file <logging-file-path>
```

## How to run last step of pipeline

It is possible to run only the last step of the pipeline. In this step, insights such as justification and examples for each category are generated.

Run as `main_insights.py` follows:
```
python main_insights.py --git_data_path <file-ending-with-"_summary.csv">
```

## Final results

Run the following bash scripts to get statistics and a final CSV with all analyses:
```
bash per_group_statistics.sh <path-with-analyses>
bash per_group_analyses.sh <path-with-analyses>
```

## Example of `csv-grouping-file`:

| org_name   | proj_name         | id     | repo_id | group_name                   | created                  | updated                  |
|------------|-------------------|--------|---------|------------------------------|--------------------------|--------------------------|
| WM-Omnigo  | Omnigo.LPR        | 117370 | 123682  | iTrak and ReportExec-Production | 2025-02-14 12:16:29.282859 | 2025-02-17 11:54:10.373370 |
| WM-Omnigo  | Omnigo.Nibrs      | 117369 | 123681  | ITI and ReportExec-Production   | 2025-02-14 12:16:26.716019 | 2025-02-17 11:54:10.538395 |
| WM-Omnigo  | Omnigo.ReportExec | 117361 | 123673  | ReportExec-Production           | 2025-02-14 12:02:40.196524 | 2025-02-17 11:54:10.872026 |

IMPORTANT: Make sure that you test your changes on repository groupings as well.
