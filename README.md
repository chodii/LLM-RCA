
Assuming the repository is cloned into .\src\ folder.
## Unpack if necessary
cd .\src\General\
python .\data_unpack.py C:\Datasets\OriginalFolderWithArchives\ C:\Datasets\dataset\ --delete-archives

## Find anomalies
cd .\src\DES\DataPreprocessing\Window\
python textsniffer_simplified_nonbinary.py C:\Datasets\dataset\

This shall produce something like .\out\restart_incidents.json


## Connect Issues
cd .\src\General\
python .\xlsx_main_pipeline_top_compact.py 'C:\Datasets\issues__.xlsx' ..\DES\DataPreprocessing\Window\out\restart_incidents.json

## Chunking
cd .\src\DES\DataPreprocessing\
python .\AllChunker.py -r C:\Datasets\dataset_orig\ -d C:\Datasets\dataset_processed\ -c 5000

This will produce out\5000\chunked_incidents.json, as chunking is set to 5000 characters.
For more information, and options use --help.

## Experiments
python DESExperiments.py -i .\src\DES\DataPreprocessing\out\5000\chunked_incidents.json -s
inside the ./out/ folder you will find the experiments results.

The LOGGER.json result file can be further processed using .\src\DES\DataPreprocessing\Evaluation\Logger.py
