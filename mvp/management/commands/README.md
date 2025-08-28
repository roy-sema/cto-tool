# Commands

List of available Django commands and parameters.

Invoke with `python manage.py <command> <parameters>`.

Some commands are specific to the AI Code Monitor or the CTO Dashboard.


## Common commands

### `clear_cache`

Clears Django app cache.

No parameters.


### `import_geographies`:

Imports geography data from a JSON file.

Parameters:
- `jurisdictions_file`: Path to the jurisdictions file.
- `jurisdictions_info_file`: Path to the jurisdictions info file.
- `--erase`: Erase all existing geographies before importing.


### `init_groups`:

Initialize user groups and permissions.

This command is executed after each deployment to update groups and permissions.

No parameters.


### `populate_db_dev_data`:

Populate the database with data to speed up development. The numbers are inflated to be able to detect performance issues during development.

Not intended for production.

Parameters:
- `--authors_num`: Number of authors to create.
- `--authors_attach_group_chance`: Chance of authors attaching to a group.
- `--authors_groups_num`: Number of author groups.
- `--contextualization_max_changes_per_repository`: Maximum number of changes per repository.
- `--contextualization_num_projects`: Number of projects.
- `--org_prefix`: Prefix for organization.
- `--repositories_num`: Number of repositories to create.
- `--repository_commit_max_days_ago`: Maximum days ago for repository commits.
- `--repository_attach_group_chance`: Chance of repositories attaching to a group.
- `--repository_groups_num`: Number of repository groups.
- `--repository_groups_max_rules`: Maximum number of rules per repository.
- `--repository_max_commits`: Maximum number of commits per repository.
- `--repository_max_files`: Maximum number of files per repository.
- `--repository_max_file_commits`: Maximum number of commits per file.
- `--repository_max_file_lines`: Maximum number of lines per file.
- `--repository_max_file_authors`: Maximum number of authors per file.
- `--repository_min_file_authors`: Minimum number of authors per file.
- `--repository_max_chunk_size`: Maximum chunk size.
- `--repository_min_chunk_size`: Minimum chunk size.
- `--repository_chunk_ai_chance`: Chance of AI-generated chunks.
- `--repository_chunk_ai_pure_chance`: Chance of purely AI-generated chunks.
- `--repository_chunk_max_commits`: Maximum number of commits per chunk.
- `--repository_not_evaluated_chance`: Chance of repository not being evaluated.
- `--rules_prefix`: Prefix for rules.
- `--rules_num`: Number of rules.
- `--rules_apply_org_chance`: Chance of rules applying to the organization.
- `--rules_max_conditions`: Maximum number of conditions per rule.


### `populate_data_provider_mock_data`:

Populate the database with data for codebase reports to speed up development.

Not intended for production.

Parameters:
- `--days_ago`: Days ago to start creating data.
- `--members_num`: Number of members per integration.
- `--org_prefix`: Prefix for organization.
- `--projects_num`: Number of projects per integration.
- `--record_max_value`: Max value for record.


## GenAI Radar commands

### `create_external_repositories`:

Creates an organization, moves given repositories to scan folder, adds repositories to the database, and prepares them for analysis. If the organization exists, repositories will be added to it.

This is mostly used to run codebase scans in the AICM server.

Parameters:
- `org_name`: The name of the organization to create.
- `repos_path`: The folder where the repositories are stored (each repository in one folder).


### `delete_organization_data`:

Deletes given organization data from the database and all associated files from disk and disconnects from service providers, if no organization is provided then it'll delete all organizations where `marked_for_deletion` is set to `True`.

Can also be used to (soft) delete the organization instance itself by providing `--delete-organization` flag.

This is used when a customer requests to delete their code. Using `--code-only` allows us to keep the aggregated data.

We run this at the end of our nightly updates

Parameters:
- `--orgid`: ID of the organization to delete, will affect all organizations with `marked_for_deletion=true` if not provided
- `--code-only`: Deletes only the code from the disk, leaving database records intact.
- `--delete-organization`: (Soft) Deletes the organization instance also.
- `--no-input`: no confirmations, only use in crons


### `download_repositories`:

Fetch repositories from git providers, add them to the database and clone them to disk.

This is executed by the AI cron job on the production environment.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.
- `--reponame`: Narrow execution just to given repository name.
- `--force`: Force re-download of repositories. If they exist, they will be deleted and re-downloaded.


### `fetch_pull_requests.py`:

Fetch pull requests from git providers that were not received through webhooks, and process them.

This is executed by the AI cron job on the production environment.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.
- `--providers`: Narrow execution just the given providers, takes a list separated by space


### `force_ai_engine_rerun`:

Forces the re-run of the AI Engine for the last analysis of the given organization.

Parameters:
- `orgid`: ID of the organization to re-run analysis.
- `--repoid`: Narrow execution just to given repository ID.
- `--commit_sha`: Re-run analysis on this SHA instead of the last one.
- `--redownload`: Force re-download of files. If they exist, they will be deleted and re-downloaded.


### `get_pull_request_report`:

Creates a report of processed Pull Request for given organization.

Parameters:
- `orgid`: ID of the organization to check.


### `import_ai_engine_data`:

Imports AI Engine data from CSV for full scans.

This is executed by the AI cron job on the production environment.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.
- `--repoid`: Narrow execution just to given repository ID.
- `--commit_sha`: Narrow execution just to given SHA.
- `--erase`: Erase existing analysis from the database before importing.


### `import_pull_request_ai_engine_data`:

Imports AI Engine data from CSV for given Pull Request.

This command is only for manual execution, it is not used in the production environment.

Parameters:
- `prid`: Import given PR ID (not number).
- `--erase`: Erase existing PR analysis before importing.


### `recalculate_attested_ai_composition`:

Obtains list of commits that have been attested and then Recalculates pre-computed AI fields for the commits and their related PRs, repositories and groups.

This is executed by a cron job on the production environment.


### `recalculate_commits_ai_composition`:

Recalculates pre-computed AI fields for commits and their related PRs, repositories and groups.

This is used in case there's something wrong with the AI fields and they need to be recalculated.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.
- `--repoid`: Narrow execution just to given repository ID.
- `--commit_sha`: Narrow execution just to given SHA.
- `--force`: Force re-calculation on all files, not just those that need it according to attestation.
- `--all`: Recalculate all commits for all organizations (very Expensive, use with caution).


### `recalculate_groups_ai_fields`:

Recalculates pre-computed AI fields for repository and developer groups."

This is used in case there's something wrong with the AI fields and they need to be recalculated.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.


### `regenerate_gbom`:

Regenerates pre-computed GBOMs.

This is used in case there's something wrong with the GBOMs and they need to be regenerated.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.


### `resend_webhook`:

Resends webhook. Useful for testing purposes and reprocessing failed webhooks.

This is used in case there's a problem with the webhook and it needs to be reprocessed.

Parameters:
- `json_path`: Path to the webhook JSON file.
- `endpoint_url`: URL to send the webhook to.

Production example:

```shell
python manage.py resend_webhook /home/cto-tool/webhook-data/webhook.json https://app.semasoftware.com/api/webhook-azure-devops/
```

Local example:

```shell
python manage.py resend_webhook ./webhook-data/webhook.json https://smee.io/abcd123
```


### `send_daily_message_email`:

Sends Daily Message emails to all users that have the `compass_anomaly_insights_notifications` flag set.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.


### `send_compass_summary_insights_emails`:

Sends Compass Summary Insights emails to all users that have the `compass_summary_insights_notifications` flag set.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.


### `shred_code`:

Deletes code from disk for commits created more than 30 days ago. Excludes open Pull Requests and the last commit of each repository.

This is executed by the AI cron job on the production environment.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.


## Engineering Radar commands

### `calculate_scores`

Calculates daily Sema score for all organizations.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.
- `--erase`: Erase all existing scores.


### `fetch_data`:

Fetches data from an integrated API.

Parameters:
- `provider`: Name of the provider to fetch data from.
- `--orgid`: Narrow execution just to given organization ID.


### `import_compliance_standards_csv`:

Imports compliance standards from CSV.

Parameters:
- `csv_file`: Path to the CSV file to import.


### `import_license_csv`:

Imports reference data from CSV.

Parameters:
- `csv_file`: Path to the CSV file to import.


### `import_reference_metrics_csv`:

Imports reference metrics data from CSV.

Parameters:
- `csv_file`: Path to the CSV file to import.


### `import_reference_records_csv`:

Imports reference records data from CSV.

Parameters:
- `csv_file`: Path to the CSV file to import.


### `copy_repository_languages_to_commits`::

Populates the `languages` field in the RepositoryCommit objects from the related Repository object.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.
- `--repoid`: Narrow execution just to given repository ID.
- `--force`: Force copy even if the field is already populated.


### `sync_users_with_mailchimp`:

Syncs users that have at least one organization and is not staff with Mailchimp mailing list.


### `create_mailchimp_audience`:

Creates a mailchimp audience for the purpose of testing locally.
You'll need to add the list ID returned by the command to the `MAILCHIMP_AUDIENCE_LIST_ID` env.

Parameters:
- `name`: Name of the mailchimp audience you wish to create.


## Product Roadmap Radar Commands

### `experiment_contextualization_script`:

Runs the contextualization script for the given organization.

Parameters:
- `--orgid`: Narrow execution just to given organization ID.
- `--day-interval`: Day interval to run the pipelines for. accepted values [1, 7, 14]. default: 14
- `--pipelines`: Specific pipelines to run. Any of : 'a', 'bc', 'anomaly_insights', 'd'.
- `--import-only`: Only imports the data, doesn't run the pipelines.
- `--dry-run`: Don't save any data, just show what commands would be executed.
- `--force_anomaly_insights`: Save insights even if it has already been executed today.
- `--force-pipeline-a`: Don't use cached results in db and update them.


### DEPRECATED

These commands are not used anymore:

- `get_snyk_issues`
- `increment_component_version`
