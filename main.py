"""
The script to run all experiments in parallel.
"""

from experiment import run_experiment
from joblib import Parallel, delayed, cpu_count


# Experiment names and dataset paths
# dl10   -> distance limit is 10
# nfl50  -> number of files limit is 50
# sws365 -> sliding window size is 365
experiments = [
    ("pig_dl10_nfl50_sws365", "data/pig_change_sets.json"),
    ("hive_dl10_nfl50_sws365", "data/hive_change_sets.json"),
    ("hadoop_dl10_nfl50_sws365", "data/hadoop_change_sets.json"),
]

# Run all in parallel using all CPUs.
Parallel(n_jobs=-1)(
    delayed(run_experiment)(experiment_name, dataset_path)
    for experiment_name, dataset_path in experiments
)
