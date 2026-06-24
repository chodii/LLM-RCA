# Agentic RCA

LLM-based agent for multi-artifact Root Cause Analysis (RCA) of issues in railway-vehicle
log files — the codebase behind the master's thesis *"LLM for Multi-Artifact Root Cause
Analysis of Issues"*.
Be aware: **This code is built towards a specific non-public dataset.**
The dataset this code was adapted to contains various log files from a distributed embedded system.

## Install

From the repository root:

```
pip install -e .
```

## Environment variables

The RCA agent and database loader/fetcher expect these environment variables to be set:

```
$env:OPENROUTER="your-openrouter-api-key"
$env:MONLIS_DBNAME="monlis"
$env:MONLIS_USER="chody"
$env:MONLIS_DB_PSW="your-postgres-password"
```

## Database setup

Create the PostgreSQL database and user first if they do not already exist:

```
createuser --pwprompt $env:MONLIS_USER
createdb -O $env:MONLIS_USER $env:MONLIS_DBNAME
```

Before loading chunks or running the RCA agent, initialize the PostgreSQL schema with:

```
psql -U $env:MONLIS_USER -d $env:MONLIS_DBNAME -f src/rca/ai_agent/knowledge_base/db_init.sql
```

## Unpack
If you work with the raw dataset, it contains many archives, often recursively compressed, unpack them automatically using:
```
python -m rca.data_preprocessing.dataset_acquisition.data_unpack C:\Datasets\OriginalFolderWithArchives\ C:\Datasets\dataset\ --delete-archives
```

## Identify issues
Use my dataset-specific issue identification:
```
python -m rca.data_preprocessing.timestamps_incidents.TextSniffer C:\Datasets\dataset\
```

## Connect identified issues with those known previously
Connect issues identified in the previous step with those listed in the .xlsx file exported from the ticketing system.
```
python -m rca.data_preprocessing.evaluation_set.xlsx_main_pipeline_top_compact 'C:\Datasets\MonLis\Summary of AVENTRA_CRO issues____.xlsx' .\out\events-EMERGENCY-MPSPThreads-Restart.json
```

## Chunk the dataset
Transform the raw data into a dataset.
This is done by selecting for each incident only its relevant log files with relevant log lines, and chunk it to selected size (e.g. 3000 characters):
```
python -m rca.data_preprocessing.chunking.AllChunker -r C:\Datasets\dataset\ -d C:\Datasets\dataset_processed\ -c 3000
```


## Assess potential performance achievable from the dataset
As running experiments does some evaluation in the process, a potential performance needs to be assessed by analyzing the coverage between the reference (target) RCA and the dataset.
```
python -m rca.ai_agent.experiments.DESExperiments -i ./out/3000/chunked_incidents.json -a
```

## Run on validation set (20% of the dataset)
Don't burn your tokens recklessly, try on a subset of the dataset:
```
python -m rca.ai_agent.experiments.DESExperiments -i ./out/3000/chunked_incidents.json -s -v
```

## Run on the remaining 80% of the dataset
```
python -m rca.ai_agent.experiments.DESExperiments -i ./out/3000/chunked_incidents.json -s
```
