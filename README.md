# CTO Tool MVP

## Table of Contents
- [CTO Tool MVP](#cto-tool-mvp)
  - [Table of Contents](#table-of-contents)
  - [Development](#development)
    - [Pre-requisites](#pre-requisites)
      - [Make sure sema DB is created](#make-sure-sema-db-is-created)
    - [Installation](#installation)
    - [Linters](#linters)
      - [Pre-commit Setup](#pre-commit-setup)
      - [IDE Setup](#ide-setup)
    - [GitHub App configuration](#github-app-configuration)
  - [Contribution guide](#contribution-guide)
    - [Discussion](#discussion)
    - [Documentation](#documentation)
    - [Code review](#code-review)
    - [Check for N+1 issues](#check-for-n1-issues)
    - [Use GenAI](#use-genai)
  - [Tests](#tests)
  - [Cache](#cache)
  - [Admin](#admin)
  - [Authentication](#authentication)
  - [API Implementation](#api-implementation)
  - [Django Commands](#django-commands)
  - [GitHub Status Check](#github-status-check)
    - [GitHub Status Check Development and Testing](#github-status-check-development-and-testing)
  - [Azure DevOps integration and testing](#azure-devops-integration-and-testing)
    - [1. Create Azure Token](#1-create-azure-token)
    - [2. Configure webhooks](#2-configure-webhooks)
    - [Maintenance mode](#maintenance-mode)
  - [To use the CTO-Tool with BitBucket repositories the following steps are needed:](#to-use-the-cto-tool-with-bitbucket-repositories-the-following-steps-are-needed)
    - [Create a BitBucket Oauth2 consumer](#create-a-bitbucket-oauth2-consumer)
    - [1. Install Sema BitBucket OAuth consumer for a workspace](#1-install-sema-bitbucket-oauth-consumer-for-a-workspace)
    - [2. Set up webhooks proxies](#2-set-up-webhooks-proxies)
  - [Jira integration and testing](#jira-integration-and-testing)
    - [Create a Jira Oauth2 consumer](#create-a-jira-oauth2-consumer)
  - [Compass document storage](#compass-document-storage)
    - [Testing Compass document upload to s3 locally](#testing-compass-document-upload-to-s3-locally)
      - [How to create your own s3 bucket](#how-to-create-your-own-s3-bucket)
  - [Frontend (Vue)](#frontend-vue)
    - [Standalone](#standalone)
      - [Development](#development-1)
      - [Deployment](#deployment)
  - [AI Code Monitor (AICM)](#ai-code-monitor-aicm)
    - [Analyze GenAI code](#analyze-genai-code)
      - [Force GBOM re-generation](#force-gbom-re-generation)
      - [Set up a cron](#set-up-a-cron)
    - [Import Geographies](#import-geographies)
    - [Import Compliance Standards](#import-compliance-standards)
    - [Delete Organization Data](#delete-organization-data)
  - [Executive Summary, Product Detail \& Compliance Detail](#executive-summary-product-detail--compliance-detail)
    - [Fetch data from the API integrations](#fetch-data-from-the-api-integrations)
      - [Set up a cron](#set-up-a-cron-1)
    - [Calculate scores](#calculate-scores)
  - [Deployment](#deployment-1)
    - [Manual deployment](#manual-deployment)
  - [Apache configs](#apache-configs)
  - [Mailchimp](#mailchimp)
  - [Add a new Custom Field to the Audience](#add-a-new-custom-field-to-the-audience)
- [Coding standards](#coding-standards)
  - [Migrations](#migrations)
- [OpenTelemetry](#opentelemetry)
  - [Example running django server with opentelemetry](#example-running-django-server-with-opentelemetry)
  - [Example running contextualization pipelines with opentelemetry](#example-running-contextualization-pipelines-with-opentelemetry)
  - [Example running contextualization pipelines with opentelemetry but with a testing environment](#example-running-contextualization-pipelines-with-opentelemetry-but-with-a-testing-environment)
- [Recording and replaying LLM requests for faster development and testing](#recording-and-replaying-llm-requests-for-faster-development-and-testing)
    - [Running End-to-End Tests Locally](#running-end-to-end-tests-locally)
      - [Prerequisites](#prerequisites)
      - [Running the `TestDailyPipelineE2E` test](#running-the-testdailypipelinee2e-test)

This is the first iteration of the CTO Tool product.

## Development

Environment:

- Python 3.12
- Node 20.13
- PostgreSQL 16 (with TimescaleDB)
- UV 0.7.12
- Git LFS

We have `django_extensions` and `ipython` installed, so you can use the `shell_plus` command to have all models imported
and use all the features of ipython.

https://django-extensions.readthedocs.io/en/latest/

https://ipython.org/ipython-doc/3/index.html

### Pre-requisites

We use [timescaledb](https://www.timescale.com/) for the database, you can install it locally by guide [here](https://docs.timescale.com/self-hosted/latest/install/). The easiest way would be to use the docker image.

IMPORTANT: **The application will not run properly without timescaledb**.
```shell
docker pull timescale/timescaledb-ha:pg17
docker run -d --name timescaledb -p 5432:5432 -e POSTGRES_PASSWORD=postgres timescale/timescaledb-ha:pg17
```
> Note: if you have postgres running locally you can change the port to something else like `5433:5432`

#### Make sure sema DB is created
```shell
# once timescaledb is running (after docker run command listed above)
$ docker exec -it timescaledb psql -c "CREATE DATABASE sema;"  # create the "sema" database
```

### Installation

1. Install Git LFS:

```sh
# On macOS with Homebrew
brew install git-lfs

# On Ubuntu/Debian
sudo apt-get install git-lfs

# On Windows, download from https://git-lfs.github.io/
```

2. Initialize Git LFS in the repository:

```sh
git lfs install
```

3. Pull LFS files:

```sh
git lfs pull
```

4. Install requirements:

```sh
uv sync --all-groups
npm install
```

5. Set the environment variables. On local copy `.env.local` to `.env`.

6. Activate the virtual environment:

```sh
source .venv/bin/activate
```

7. Run migrations:

```sh
python manage.py migrate
```

8. Run Django development server:

```sh
python manage.py runserver
```

9. Create a Django admin user:

```sh
python manage.py createsuperuser
```

10. Create cache table:

```sh
python manage.py createcachetable
```

11. Initialize groups and permissions:

```sh
python manage.py init_groups
```

12. Run the frontend:

```sh
cd vue-frontend
npm install
npm run build
npm run dev
```

13. Collect static files:

```sh
python manage.py collectstatic
```

14. (Optional) Populate the database with data to speed up development:

```sh
python manage.py populate_db_dev_data
```

15. Create and set the organization to your user using our signup flow



### Linters

We use [Ruff](https://github.com/astral-sh/ruff) with pre-commit for linting and formatting.

#### Pre-commit Setup

- Install cto-tool uv dependencies: `uv sync --all-groups`
- Run `uv run pre-commit install` in cto-tool repo to set up pre-commit hooks. They will now run automatically when you commit

#### IDE Setup

[Install ruff for your IDE](https://docs.astral.sh/ruff/editors/setup/)

> If using VSCode, it's recommended to open the project by going to `File -> open workspace` and selecting the `cto-tool.code-workspace` file.
> this will ensure that vscode loads both settings.json files in case you want to also work on the frontend from the same window.

### GitHub App configuration

You will need to create a GitHub app for development purposes.

Steps to create a GitHub app:

1. [Create a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
2. Name and Homepage URL can be anything you want
3. In the Github app's **"Identifying and authorizing users"** section, set the following:
   - Set callback URL to `http://127.0.0.1:8000/settings/connect/github/`
4. In the Github app's **"Post-installation setup URL"** section:
   - Set the post-installation setup URL to `http://127.0.0.1:8000/settings/connect/github/`
   - Check `Redirect on update`
5. Webhook: check `Active` and set the Webhook URL to a proxy URL to your machine:
   - Use https://smee.io/ or https://ngrok.com/ to create a proxy to your machine
   - The webhook proxy should point to `http://127.0.0.1:8000/api/webhook-github/`
   - If using smee.io, a useful command to run is `npx smee-client -u https://smee.io/<path-parameter> -t http://127.0.0.1:8000/api/webhook-github/`
     This creates a UI to see events coming in at page: `https://smee.io/<path-parameter>`
     Note: `<path-parameter>` is a random string generated by the user. For example `7urfghqofEfIVfdX`
6. In the GitHub app's **"Permissions"** section, set the following permissions and under **"Repository permissions"** section:
   - Contents: `Read-only`
   - Checks: `Read & Write`
   - Pull requests: `Read & Write`
7. In the Github app's **"Subscribe to events"** section, set the following:
   - Subscribe to events: `Pull request`
8. Click `Create GitHub App`
9. In the Github app's **"Private key"** section,
   - Click `Generate a private key`
10. Make the app public
11. Remember to set `Status check enabled` for the Organization in the AICM, either through Settings view or Django Admin

Once the app created, update the app details in .env file and restart the django app.

To check it's working:
1. Make sure you have personal repositories created on your GitHub account. Tip: fork any public repo
2. Go to `http://127.0.0.1:8000/settings/connections/` and connect your GitHub account
3. Select one or more repositories
4. The app should start downloading the last commit of the selected repositories to your local disk

## Contribution guide

Since this is a small team project, we'll be using [Trunk-Based Development](https://trunkbaseddevelopment.com/).

Workflow:

- Create a new branch for a new feature.
- Each branch should be named after a Jira task (like `SIP-XXX-Name-of-task`).
- When done, open a PR.
- A PR needs to be approved before merging to `main`.
- Branches should be short-lived (a few days)
- The PR should also be named after a Jira Task

TL;DR: Create a branch for each ticket, open a PR against `main`.

### Discussion

When creating a new endpoint, feature, or complex task, all developers should discuss it before starting to code.

Actions:
- During stand-up, the assignee of the task will say "let's talk about this task after stand-up"
- On the ticket, let's add a "needs discussion" reminder

### Documentation

There's no much documentation. We want to increase our documentation and minimize outdated documentation.

Actions:
- Document the code when a class or function. General rule of thumb: ask yourself, "If I come back to this code in 6 months, will I understand it?" If the answer is no, document it.
- When there's architectural or complex documentation, let's create a Confluence page and link it to the code so we remember to update it.
- When someone explains something to you, take notes so you can update/create documentation.
- When you explain something to someone, ask them to take notes so they can update/create documentation.
- When we create/review tickets, let's link any existing documentation. If there's none, consider adding some.

### Code review

At the stage we are, we need to ship features faster. Thus, we'll have a more relaxed code review process.

To minimize breaking production—since there's no staging environment—we'll create e2e tests with [bugbug.io](https://bugbug.io/) for crucial features.

How to code review:
1. First, pull the branch to your local and test whether the feature works or not as described in the ticket.
2. Then, look at the code.
3. Prepend an emoji to comments to make code review faster:
    - 🍷🧀 For suggestions, nice to haves, "taste" or opinionated comments.
    - 🚨🔥🐛 For comments that need to be fixed.
    - 👏🙏 For showing appreciation, for example for nice code or to say "thank you" for something you requested.
4. Unless there are 🚨🔥🐛 comments, approve the PR to avoid blocking the merge.

### Check for N+1 issues

Due to Django ORM, it's very easy to create N+1 queries.

Since we deal with repositories with many files and chunks, we need to fix N+1 queries before going to production since they will most likely cause issues on large repositories.

We have several ways to detect them:
- When loading a Django Template view: expand the integrated Debug Toolbar on the right side
- When loading an API view: use [Silk](http://127.0.0.1:8000/silk/) or check the API request, example: http://127.0.0.1:8000/api/repositories/composition/

In production, we'll have Sentry [detecting N+1 queries](https://docs.sentry.io/product/issues/issue-details/performance-issues/n-one-queries/) too.


### Use GenAI

We are aiming to a 30% of GenAI usage in this repo to help us deliver features faster.

Sema can provide license for Copilot or other tools if needed.

There are many tasks that LLMs do well, you can check [these examples](https://semalab.atlassian.net/wiki/spaces/ACD/pages/2973401137/CAW+Onboarding#Using-AI-for-coding).

To make sure we are using GenAI, remember to attest your PRs.

Guide to attest:
- If the chunk contains ONLY GenAI code, attest it as Pure.
- If the chunk contains GenAI code and NotGenAI code, attest it as Blended.
- If the chunks doesn't contain GenAI code, attest it as NotGenAI.
- If the chunk contains GenAI BUT also contains lines from other developer, attest it as Blended.
- If the chunk ONLY contains lines from other developer, don't attest it.


## Tests

NOTE: We only have some unit tests at the moment. Proper tests for all views are missing.

To run tests:

```sh
python manage.py test
```

You can run single tests like this:

```sh
python manage.py test mvp.tests.test_views.test_members_view
```

Or even more granular:

```sh
python manage.py test mvp.tests.test_views.test_members_view.MembersViewTest.test_user_member_list
```

you can also have the tests run in parallel

```sh
python manage.py test --parallel
```

or define the number of cores to run the tests on

```sh
python manage.py test --parallel 4
```

## Cache

This site uses Django's cache framework to cache some data.

In production this is cleared daily with the following command executed by a cron:

```sh
python manage.py clear_cache
```

In development cache applies as well, clear it manually if needed.


## Admin

The admin path has been renamed to offer some level of security through obscurity:

`http://127.0.0.1:8000/admin-does-not-live-here/`


## Authentication

This project uses [allauth](https://docs.allauth.org/en/dev/index.html) for authentication.

The main reason is MFA support.

Most templates are overriden, check:
- `mvp/templates/account/*`
- `mvp/templates/allauth/*`
- `mvp/templates/mfa/*`
- `mvp/templates/recovery_codes/*`

Further customization:
- Custom sign up view with invite token support: `cto-tool/mvp/views/signup_view.py`
- Password history enforcement: `mvp/models.py`
- Set session expiration time and on browser quit: `mvp/settings.py`
- Some allauth URLs are disabled: `mvp/urls.py`

IMPORTANT: authentication has been adjusted for SOC-2 compliance. Before changing anything related to authentication, make sure it complies with the requirements.


## API Implementation

Note: All data models which will be exposed through API will use public_ids (hashed) which are different from model
ids/pks to mitigate possible attacks from attackers.


## Django Commands

Check the [list of available commands](mvp/management/commands/README.md).


## GitHub Status Check

For GitHub status check run, GitHub app needs to have webhook active and with
the proper URL and secret

you will need your app to have those permissions

- content (read)
- pull request (read)
- check (read/write)

and it should subscribe to `pull request` events

### GitHub Status Check Development and Testing

To test the status check on local you can use https://smee.io and start a new channel
from the website
then set the given url by the channel as your app's webhook (
i.e. https://smee.io/7urfghqofEfIVfdX) and set your secret too

On your local, you can install `smee-client` locally with npm or just use `npx` like

```shell
npx smee-client -t http://127.0.0.1:8000/api/webhook-github/ -u https://smee.io/7urfghqofEfIVfdX
```

and it should forward the events to your local

you'll also need to add `smee.io` to your `ALLOWED_HOSTS` in `.env`

```dotenv
ALLOWED_HOSTS="127.0.0.1,localhost,smee.io"
```

## Azure DevOps integration and testing

To use the tool with Azure Devops and Azure Repos the following steps are needed:

### 1. Create Azure Token

Go to dev.azure.com
Click on the top right corner and go to personal access tokens.

Create a token (set expiration as you deem fit, you will have to recreate it when it expires).

Paste the token in Connect Azure DevOps settings view:
http://127.0.0.1:8000/settings/connect/azure_devops/


### 2. Configure webhooks

We need to configure service hooks so that our system is notified about the events and trigger the right flow for the tool to kick in.

In your azure devops project click on project settings > service hooks and then select web hooks from the list and click next.

Select the repository you want to integrate the tool with. Add the following 4 events for the repository (or project)

- Pull request created
- Pull request updated

Add `/api/webhook-azure-devops/` as the endpoint for the webhook.


### Maintenance mode

You can enable maintenance mode on the server by creating a file
called `maintenance.enabled` in the root of the project (`/home/cto-tool/cto-tool/`).

there should already be a file called `maintenance.enabled.not` so to enable maintenance
mode you can just do

```shell
mv maintenance.enabled.not maintenance.enabled
```

and to disable it again

```shell
mv maintenance.enabled maintenance.enabled.not
```

you should not need to `restart` apache, but if you want to, you can do it with

```shell
sudo service apache2 restart
```

## To use the CTO-Tool with BitBucket repositories the following steps are needed:
The BitBucket integration is built using Oauth2 and webhooks. A Centralised Oauth consumer is used to authenticate
the user and webhooks are used to notify the CTO-Tool of events happening in the repositories.

To test locally it is possible to create your own BitBucket Oauth2 consumer. To do this follow the steps below:
### Create a BitBucket Oauth2 consumer
Create an Oauth2 consumer in a BitBucket account (preferably a different account to the one you're going to pull repositories from).
Follow instructions here: https://support.atlassian.com/bitbucket-cloud/docs/use-oauth-on-bitbucket-cloud/ in the `Create a consumer` section.
Note: The Oauth flow used is `Authorization code grant` also found in this documentation.

- The Callback URL should be: `http://127.0.0.1:8000/settings/connect/bitbucket/`.
- Permissions should be:
  - `Account > Read`
  - `Workspace membership > Read`
  - `Projects > Read`
  - `Repositories > Write`
  - `Pull requests > Write`
  - `Webhooks > Read and write`
- Once the consumer is created, copy the `Key` and `Secret` and add them to the `.env` file in the `BITBUCKET_OAUTH_CONSUMER_KEY` and `BITBUCKET_OAUTH_CONSUMER_SECRET` fields respectively.

### 1. Install Sema BitBucket OAuth consumer for a workspace
BitBucket uses a centralised Sema BitBucket consumer. To install it for your workspace:
- Go to connections page under settings and follow the instructions.

### 2. Set up webhooks proxies
The BitBucket webhook will need to point to the CTO-Tool.
If developing locally you'll have to set up a proxy pointing to this URL.
- Use https://smee.io/ or https://ngrok.com/ to create a proxy to your machine
- The webhook proxy should point to `http://127.0.0.1:8000/api/webhook-bitbucket/`
- Set the `BITBUCKET_WEBHOOK_PROXY_URL` environmental variable to point to your proxy. This will be stored in the BitBucket webhook when the connection is made.
- If using smee.io, a useful command to run is `npx smee-client -t http://127.0.0.1:8000/api/webhook-bitbucket/ -u https://smee.io/<path-parameter>`

## Jira integration and testing
The Jira integration is built using Oauth2. A Centralised Oauth consumer is used to authenticate
the user. On a connection request Jira provides an auth_code. This auth_code is then used to generate
an access token and refresh token pair which is stored in the data connection model. A further request
is made to Jira to get which resources the user has access to. The cloud_id, from this call, is stored in
the data connection. Once the connection is made we can make requests to the Jira API on behalf of the user.

To test locally it is possible to create your own Jira Oauth2 consumer. To do this follow the steps below:
### Create a Jira Oauth2 consumer
Create an Oauth2 consumer in a Jira account (preferably a different account to the one you're going to pull data from).
Follow instructions here: https://developer.atlassian.com/cloud/oauth/getting-started/enabling-oauth-3lo/. But the basic
steps are:
- Navigate to https://developer.atlassian.com/console/myapps/.
- In the `create` dropdown select `OAuth 2.0 integration` and enter a name for the app. For example `sema-testing`.
- Select `Distribution` in the left pane and click `edit`.
- Under `Distribution Status` make sure `Sharing` is selected and click `Save`.
- Select `Permissions` in the left pane and click `Add` then `Configure` The permissions should match what is defined in
  [The JiraAPI class](compass/integrations/apis/jira_api.py). (most of them are under `User identity API` and `Jira API`). If you need more permissions than are already set they
  must be updated in the JiraAPI class and the Oauth2 consumer. Now click `Save`.
- Select `Authorization` in the left pane and click `Add`.
- In `Callback URL` enter the same URL as set in the `.env` file for `JIRA_OAUTH_REDIRECT_URL`. You'll need to set up
  a proxy to point to your local machine. This can be done with `ngrok`. The path for this URL should be
  `/compass/api/v1/integrations/connect-jira-redirect/`.
  For example `https://000d-2a00-23ee-2870-202-846b-ad72-886f-c8a8.ngrok-free.app/compass/api/v1/integrations/connect-jira-redirect/`.
  Now click `Save`.
- You also need to add your `ngrok` URL to to your `ALLOWED_HOSTS` in `.env`.
  For example: `ALLOWED_HOSTS="127.0.0.1,localhost,000d-2a00-23ee-2870-202-846b-ad72-886f-c8a8.ngrok-free.app"`
- Select `Settings` in the left pane. Under `Authentication details` you will see `Client ID` and `Client secret`.
  Copy these values and add them to the `.env` file in the `JIRA_OAUTH_CONSUMER_KEY` and `JIRA_OAUTH_CONSUMER_SECRET`
  fields respectively.
- Set up should be done and you should be able to connect to jira from `/settings/connections`.

## Compass document storage
Compass documents are stored in s3 for production. For local development these files are stored in the `s3_bucket` folder.
In production public access to the s3 bucket is blocked. A pre-signed URL is generated for each file that is requested.

### Testing Compass document upload to s3 locally
If you need to test s3 functionality locally you can create your own s3 bucket and set the `AWS_S3_FORCE_UPLOAD_TO_BUCKET`
environmental variable to `True`.

#### How to create your own s3 bucket
You'll need to create a s3 bucket in your AWS account.
You can follow the instructions here: https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-bucket.html.
Settings for the bucket should be:
- Object Ownership > ACLs disabled (recommended)
- Block Public Access settings for this bucket > Block all public access
- Default encryption > Server-side encryption with Amazon S3 managed keys

NOTE: you shouldn't have to add a bucket policy as all public access is blocked.

Once you have created the bucket you'll need to set up an IAM user with permissions to access the bucket:
To create an IAM user follow the instructions here: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_create.html.
Once you have your IAM setup you'll be to generate a key and secret for the user. This will be used to access the s3 bucket.
To create a key and secret follow the instructions here: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html#Using_CreateAccessKey.
Make a note of the key and secret as you'll need them to set up the `.env` file.
Now add the following to your `.env` file:
```dotenv
AWS_ACCESS_KEY_ID=<aws_access_key_id>
AWS_SECRET_ACCESS_KEY=<aws_secret_access_key>
AWS_STORAGE_BUCKET_NAME=<aws_storage_bucket_name>
AWS_S3_REGION_NAME=<aws_s3_region_name>
AWS_S3_FORCE_UPLOAD_TO_BUCKET=True  # This will force local upload to the bucket
```

Now go to the upload compass documents URL `http://127.0.0.1:8000/compass/onboarding/upload-documents` and upload some files.
You should see a success message and the files should be uploaded to your s3 bucket.
You can check this by going to the s3 bucket in your AWS account.
You can also check if the local API is correctly generating pre-signed URLs by going to `http://127.0.0.1:8000/compass/api/v1/documents/`.

## Frontend (Vue)

This app was initially built with Django templates, but we are slowly transitioning to Vue.

### Standalone

You can use Vue as a standalone app, the app should be in the `vue-frontend/src` directory

To create a new Vue app, modify the app entry point in `vue-frontend/src/app.ts` and add the new page to the `pages` object.

```ts
const pages = {
    //...
    '/new-page/': NewPage,
};
```

To send data between django and vue, you can use the `data-` attributes in the html tags, for example

```html
<div id="vue-app" data-repo-id="{{ repo_id }}" data-repo-name="{{ repo_name }}">
```
which will be then accessible in your vue as props in `camelCase` under the names `repoId` and `repoName`.

or just add an api endpoint and fetch them from vue

#### Development

To run the Vue app in development mode, run the following commands:

```shell
cd vue-frontend
npm install
npm run dev
```

which will run it on `http://127.0.0.1:5173` and django will be able to access it from
the template by using a template tag like

```html
  <script type="module" crossorigin src="{% vue_bundle_url 'app' %}"></script>
```

`vue_bundle_url` is a custom template tag that will generate the correct url for the vue
bundle depending on the environment.

for more info check the [readme in the vue-frontend directory](vue-frontend/README.md)

#### Deployment

Running the build command `npm run build` will output the build files to django's
statics directory `mvp/static/vue` which then gets collected by django's `collectstatic`
command.



## AI Code Monitor (AICM)

Check here supported languages and label definitions:
https://semalab.atlassian.net/wiki/x/B4DCq

### Analyze GenAI code

NOTE: running the AI Engine locally will allow you to have real data in your database.
If you just started developing, skip this section and instead, run the command `populate_db_dev_data`

The AI Engine is separate repository: https://github.com/Semalab/ai_engine

If you haven't done it already, clone and setup the AI Engine.

To analyze a repository:

1. Download the code of the repository to analyze.

You can download from GitHub if connected, running this command:

```sh
python manage.py download_repositories
```

NOTE: this will apply to all organizations. To narrow it to just one, use `--orgid <org_id>`.

Or you can clone a git repository manually:

```sh
git clone ssh://git@<repository_url>
```

If you get an error `fatal: detected dubious ownership in repository`, run:
```sh
git config --global --add safe.directory '*'
```

2. Run the analyzer. Check the README.md in the AI Engine repository for more details.

3. Import the data to the database:

```sh
python manage.py import_ai_engine_data
```

NOTE: this will apply to all organizations. To narrow it to just one, use `--orgid <org_id>`.

After importing the data, the script will generate the pre-computed GBOM.


#### Force GBOM re-generation

Sometimes we change GBOM format and we need to re-generate them. To do that, run:

```sh
python manage.py regenerate_gbom
```

NOTE: this will apply to all organizations. To narrow it to just one, use `--orgid <org_id>`.


#### Set up a cron

To fetch automatically, set up a cron to fetch data daily.

In production we have a script that runs the download command daily:

```sh
sudo -u cto-tool /home/cto-tool/cron.sh
```

Then another cron that runs every 15 minutes:

```sh
sudo -u cto-tool /home/cto-tool/cron_ai_engine.sh
```

The reason to have the 15 min periodically is that users can connect their GitHub account at any time.
Upon connection, the user's repositories are downloaded immediately.

The crons are set with:

```sh
crontab -e -u cto-tool
```

### Import Geographies

There is a script to import Geographies from the JSON files, to run it call

```shell
./manage.py import_geographies mvp/data/jurisdictions.json mvp/data/jurisdictions_info.json
```

### Import Compliance Standards

There is a script to import the compliance standards from a `.csv`/`.tsv` file, the script can be called with

```shell
./manage.py import_compliance_standards_csv taxonomy.tsv
```

> Note: This is supposed to be a one-time import since it wipes out all the previous entries

### Delete Organization Data

There is a script to delete organization data, it'll do the following

- Delete all organization full-scan repositories on disk
- Delete all organization pull-request repositories on disk
- Disconnect the organization from GitHub and remove the app
- Delete all models related to the organization
- Does **NOT** delete the Organization itself and any user associated with it

```shell
./manage.py delete_organization_data <org_id> # 7 for example
```


## Executive Summary, Product Detail & Compliance Detail

The folders below used to belong to the "CTO Dashboard" section:

- `mvp/insights`
- `mvp/templates/mvp/insights`
- `mvp/widgets`


The views they create have been incorporated to the AICM. In the sidebar:

- Executive Summary
- Product Detail
- Compliance Detail

To populate data for those, follow the instructions below.


### Fetch data from the API integrations

Run this Django command:

```sh
python manage.py fetch_data <provider>
```

NOTE: replace `<provider>` with the desired integration, example: `GitHub`
NOTE: this will apply to all organizations. To narrow it to just one, use `--orgid <org_id>`.

#### Set up a cron

To fetch automatically, set up a cron to fetch data daily.

Example:

```sh
* 2 * * * python /path/to/manage.py fetch_data GitHub
* 3 * * * python /path/to/manage.py fetch_data Snyk
```

In production we have a script

```sh
sudo -u cto-tool /home/cto-tool/cron.sh
```

The cron is set with:

```sh
crontab -e -u cto-tool
```

### Calculate scores

NOTE: If you haven't already, make sure to import metrics data from CSV; otherwise, calculated scores will be zero.
You can find CSV files and details on why we do this in Confluence [here](https://semalab.atlassian.net/wiki/spaces/ACD/pages/3332079618/Codebase+Health+Score+aka+Sema+Score+Engineering+Radar+Insights).

From Confluence, you should download two CSV files. One for reference metrics and one for reference records.
These can be imported via Django admin using the `Import` button found at the top of these pages:
http://127.0.0.1:8000/admin-does-not-live-here/mvp/referencemetric/
http://127.0.0.1:8000/admin-does-not-live-here/mvp/referencerecord/

Now after fetching data from APIs, calculate Sema scores by running:

```sh
python manage.py calculate_scores
```

Add it to the cron to calculate automatically too.

## Deployment

Deployment process described at [Release and Deployment](https://github.com/Semalab/cto-tool/wiki/Release-and-Deployment) wiki page

### Manual deployment

There's a script to deploy in production server. It pulls the code latest code from GitHub, and runs migrations.

To execute it:

1. Connect to the VPN

2. SSH to the server at 172.31.77.237

3. (ONLY WHEN REQUIRED) Update any modified `.env` vars:

```sh
sudo nano /home/cto-tool/cto-tool/.env
```

4. Execute the script

```sh
sudo /home/cto-tool/cto-tool/deploy.sh
```

## Apache configs

Since we use oAuth, we need to tell apache to pass in the headers to the app, to do this, this line was added to apache
conf

```shell
# /etc/apache2/sites-available/000-default.conf
WSGIPassAuthorization On
```

## Mailchimp

We use Mailchimp to sync users to a mailing list. This is done by cron job that runs once daily

and whenever a user signs ups.

To test locally run the `create_mailchimp_audience` management command and follow instructions.

You'll need to create an [API_KEY](https://mailchimp.com/help/about-api-keys/) and populate the `MAILCHIMP_*` environment variables in the .env file.


## Add a new Custom Field to the Audience

- Add the field to [MailChimpIntegration.CUSTOM_FIELDS](mvp/integrations/mailchimp_integration.py)
- Login to Mailchimp
- Go to "Audience"
- Select the production Audience
- Go to "Settings > Audience fields & Merge tags"
- Create the new merge field with the same configuration, and save it


# Coding standards

## Migrations

We try to keep one migration per PR if possible.

If you create a migration manually append `__manual` to the end of the migration file name. For example `0042_data_migration__manual.py`.

# OpenTelemetry

Whenever we use opentelemetry-instrument, we have to **externally** set the environment variables for opentelemetry. We can't just put them into .env file because .env is executed after opentelemetry-instrument instruments our code. Here's the description of the variables:

- `OTEL_SERVICE_NAME=SEMA-SIP` - The name of the service that will be displayed in honeycomb
- `DJANGO_SETTINGS_MODULE=cto_tool.settings` - otherwise opentelemetry cannot find the settings file
- `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` - protobuf is much more efficient than raw json so it's the default for exporting a large amount of spans
- `OTEL_EXPORTER_OTLP_ENDPOINT="https://api.honeycomb.io:443"` - the endpoint to send the data to honeycomb
- `OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=..."` - the headers to send to honeycomb. They are essentially the same as SENTRY_DSN for sentry
- `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true` - automatically instrument logging for both cto-tool and contextualization
- `OTEL_TRACES_SAMPLER="parentbased_traceidratio"` - the sampler to use. It's a parent based sampler that samples a percentage of traces but if a parent of a span is sampled, the child will be sampled too.
- `OTEL_TRACES_SAMPLER_ARG="0.1"` - the percentage of traces to sample. It must be 0.1 for the main django app because we rarely look at the traces in the main django app but we use 1 for contextualization pipelines because we want to see the traces for all of them. Note that sampling doesn't apply to logs.
- `OTEL_METRICS_EXPORTER="none"` - Disables metrics collection and is only required for the cronjobs as they do not have any useful metrics. However, the main django app should have them enabled so we do not pass this variable in the .env.production.opentelemetry file.


## Example running django server with opentelemetry

```bash
set -a && source .env.production.opentelemetry && set +a
OTEL_TRACES_SAMPLER="parentbased_traceidratio" OTEL_TRACES_SAMPLER_ARG="0.1" opentelemetry-instrument python manage.py runserver
```

## Example running contextualization pipelines with opentelemetry

```bash
set -a && source .env.production.opentelemetry && set +a
OTEL_TRACES_SAMPLER="parentbased_always_on" uv run opentelemetry-instrument python manage.py experiment_contextualization_script --orgid=1 --day-interval=14 --pipelines a bc anomaly_insights d
```

## Example running contextualization pipelines with opentelemetry but with a testing environment

```bash
set -a && source .env.test.opentelemetry && set +a
OTEL_TRACES_SAMPLER="parentbased_always_on" uv run opentelemetry-instrument python manage.py experiment_contextualization_script --orgid=1 --day-interval=14 --pipelines a bc anomaly_insights d
```

# Recording and replaying LLM requests for faster development and testing
We use VCR.py to record HTTP responses and replay them on subsequent identical requests. This helps ensure consistent behavior in development and testing.

**CASSETTES_PATH**: For local runs, we use the `CASSETTES_PATH` environment variable to specify the `.cassettes` directory, where VCR.py stores cassette files generated during development and local testing. For end-to-end (e2e) tests, we use the `.ci_cassettes` directory, which contains cassettes that are committed to Git LFS storage. These `.ci_cassettes` files are used in the CI pipeline to ensure consistent and reliable e2e test runs without making real HTTP requests.

Recorded responses are stored in the .cassettes/ directory.
If you'd like to update the recordings (e.g. re-run real LLM) but you have no new data, you can safely delete the recordings in the directory. However, it's almost never necessary because you usually want to re-run the real LLM when you change your prompt/inputs, in which case the recordings won't be reused anyway.

### Running End-to-End Tests Locally

End-to-end tests require a proper Django environment (database, settings, etc.), so you must invoke them using Django's built-in test runner.
They use a Git submodule, so after cloning the repository, make sure to also initialize the submodule.

#### Prerequisites

1. Activate your virtual environment:

   ```bash
   source .venv/bin/activate
   ```
2. Configure your environment variables in `.env`.
   Make sure the test database is specified:

   ```env
   RDS_DB_NAME=sema
   ENABLE_TEST_LOGGING=true  # Optional: enables INFO-level logging in test runs
   ```

3. Initialize the test submodule to fetch the test git repo:

   ```bash
   git submodule update --init --recursive
   ```

4. [Install Git LFS and fetch test data files](#installation)

#### Running the `TestDailyPipelineE2E` test

✅ This will automatically:

* Set up the test database
* Run all data and test setup
* Execute the pipeline without critical errors

To run **the `test_daily_pipeline_without_jira_connection` test**:

```bash
python manage.py test e2e_tests.pipeline_runs_e2e.TestDailyPipelineE2E.test_daily_pipeline_without_jira_connection
```

Or to run with a logging option:
```bash
ENABLE_TEST_LOGGING=true python manage.py test e2e_tests.pipeline_runs_e2e.TestDailyPipelineE2E.test_daily_pipeline_without_jira_connection
```

Or to run the **entire test class**:

```bash
python manage.py test e2e_tests.pipeline_runs_e2e.TestDailyPipelineE2E
```

If you'd like to run all tests in the file:

```bash
python manage.py test e2e_tests.pipeline_runs_e2e
```

#### Updating test cassettes in a pull request
If your end-to-end tests pass successfully but take a long time to run, you can automatically update ci_cassettes in the same pull request without committing them manually.

Just comment: ```/update-cassettes```on the pull request after the tests have completed.
This will trigger an automatic update of the recorded cassettes and push them directly to the same MR.

### API keys and environment variables

You need to create a file `.env` in the root directory of the repo. This must contain:

```bash
ANTHROPIC_API_KEY="<get-an-API-key>"
GOOGLE_API_KEY="<get-an-API-key>"
```
But first, ask your team to give you access to Anthropic's Console and provide you with an API key.

### AWS Setup

Install AWS CLI https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

- Get an AWS access key and secret key from the AWS console for your user.
- Run `aws configure`. Use the keys above and use `us-east-2` as default region.

---

# Mocking requests
We use VCR.py to record HTTP responses and replay them on subsequent identical requests. This helps ensure consistent behavior in development and testing.

Enabling VCR Mocking

To enable request mocking, add the following to your .env file:
```shell
# True or False. Enables mocking using VCR.
USE_HTTP_CALL_MOCKS=True
# Sets a fixed end date for consistent results when the period depends on the current date.
MOCKED_END_DATE=2025-05-09
```

⚠️ These environment variables should be used only in local development.

How It Works
• On the first run, real HTTP requests are made and responses are recorded.
• On subsequent runs, if a request matches (by method, path, and body), the stored response is replayed instead of making a real request.
