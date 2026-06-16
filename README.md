# Agentic RCA

LLM-based agent for multi-artifact Root Cause Analysis (RCA) of issues in railway-vehicle
log files — the codebase behind the master's thesis *"LLM for Multi-Artifact Root Cause
Analysis of Issues"* (`docs/main-code-comments.pdf`).

## Install

From the repository root:

```
pip install -e .
```


## Unpack
```
python -m rca.data_preprocessing.dataset_acquisition.data_unpack C:\Datasets\OriginalFolderWithArchives\ C:\Datasets\dataset\ --delete-archives
```

## Identify issues
```
python -m rca.data_preprocessing.timestamps_incidents.TextSniffer C:\Datasets\dataset615\
```

## Connect identified issues with those known previously

```
python -m rca.data_preprocessing.evaluation_set.xlsx_main_pipeline_top_compact 'C:\Datasets\MonLis\Summary of AVENTRA_CRO issues____.xlsx' .\out\events-EMERGENCY-MPSPThreads-Restart.json
```

## Chunk the dataset

```
python -m rca.data_preprocessing.chunking.AllChunker -r C:\Datasets\dataset615\ -d C:\Datasets\dataset_processed_615\ -c 5000
```

## Assess potential performance achievable from the dataset

```
python -m rca.ai_agent.experiments.DESExperiments -i ./out/5000/chunked_incidents.json -a
```

## Try running on validation set (20% of the dataset)

```
python -m rca.ai_agent.experiments.DESExperiments -i ./out/5000/chunked_incidents.json -s -v
```

## Run on the remaining 80% of the dataset

```
python -m rca.ai_agent.experiments.DESExperiments -i ./out/5000/chunked_incidents.json -s
```
