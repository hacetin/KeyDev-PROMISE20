

# Identifying Key Developers using Artifact Traceability Graphs

We study key developers under three categories: **jacks**, **mavens** and **connectors**. A typical **jack** (of all trades) has a broad knowledge of the project, they are familiar with different parts of the source code, whereas **mavens** represent the developers who are the sole experts in specific parts of the projects. **Connectors** are the developers who involve different groups of developers or teams. They are like bridges between teams.

To identify key developers in a software project, we propose to use traceable links among software artifacts such as the links between change sets and files. First, we build an **artifact traceability graph**, then we define various metrics to find key developers. We conduct experiments on three open source projects: **Pig**, **Hive** and **Hadoop**. 

This repository is the source code of [the research article](https://www.researchgate.net/publication/343712903_Identifying_Key_Developers_using_Artifact_Traceability_Graphs)  [[1]](#1) published at **PROMISE '20**. You can read it for details.

## Files

 - [preprocess.py](preprocess.py): Reads data from sqlite3 databases, runs preprocessing steps, and generates a JSON file for each dataset.
 - [data_manager.py](data_manager.py): Responsible for reading data from JSON file and controling the sliding window mechanism.
 - [graph.py](graph.py): Creates artifact graph and developer graph by using the sliding window mechanism provided by `data_manager.py`, also identifies key developers with these graphs.
 - [experiment.py](experiment.py): Supplies the experiment setup producing the results shared in the article.
 - [main.py](main.py): Runs all 3 experiments in parallel.
 - [util.py](util.py): Includes a group of functions used by different scripts.
 - [extract_commenters.py](extract_commenters.py): Extracts commenters and their comment count for each slidling window.
 - [validation.py](validation.py): Generates top-k accuracy tables shared in the article.


## Start
Clone the repo.

`git clone https://github.com/hacetin/KeyDev-PROMISE20.git`

Then, change the directory to the project folder.

`cd KeyDev-PROMISE20`

## Install required packages
Using a virtual environment is recommended while installing the packages.

Python version is "3.7.4" in our experiments. `graph.py` uses "networkx 2.4" for graph operations. `main.py` uses "joblib 0.15.1" for parallel processing of the experiments.

You can install them seperately or use the following command to install the correct versions of all required packages.

`pip install -r requirements.txt`

## Reproduce results
### Preprocess
Generate JSON files.
1) Download Hadoop, Hive and Pig datasets [[2]](#2) from [https://bit.ly/2wukCHc](https://bit.ly/2wukCHc), and extract the following files into **data** folder: 
 - hadoop.sqlite3 
 - hive.sqlite3 
 - pig.sqlite3 

2) Run the preprocess script to generate JSON files for all 3 projects (takes a few seconds per project):

   `python preprocess.py`

###  Run experiments
Run 3 experiments (for 3 projects) in parallel with the default configurations given in `main.py` (same configurations given in the article).

`python main.py`

This step can take hours depending on your system (Pig takes 4 minutes, Hive takes 43 minutes and Hadoop takes 65 minutes on my computer.). It will create a pickle file for each experiment under **results** folder to keep the key developer for each day. You can see the logs under **logs** folder.

### Run validation script

Run the validation script to generate the top-k accuracy tables shared in the article.

   `python validation.py`

## Run tests for `graph.py`, `data_manager.py` and `util.py`
By using a sample graph (data/test_data), we implemented unit tests for `graph.py` and `data_manager.py`. Also, we implemented tests for the functions in `util.py`.

Each script has own tests inside it. To run these tests, you can call them separately.

`python graph.py` or `python data_manager.py` or `python util.py`

You can inspect the sample graph step by step in [data/test_data/sample_graph_steps.pdf](data/test_data/sample_graph_steps.pdf).

## References
<a id="1">[1]</a> H. Alperen Çetin and Eray Tüzün. 2020. Identifying Key Developers using Artifact Traceability Graphs. In Proceedings of the 16th ACM International Conference on Predictive Models and Data Analytics in Software Engineering (PROMISE ’20), November 8–9, 2020, Virtual, USA. ACM, New York, NY, USA, 10 pages. https://doi.org/10.1145/3416508.3417116

Link to the article: [https://www.researchgate.net/publication/343712903_Identifying_Key_Developers_using_Artifact_Traceability_Graphs](https://www.researchgate.net/publication/343712903_Identifying_Key_Developers_using_Artifact_Traceability_Graphs)

<a id="2">[2]</a> Michael Rath and Patrick Mäder. 2019. The SEOSS 33 dataset—Requirements, bug reports, code history, and trace links for entire projects. Data in brief 25 (2019), 104005.



