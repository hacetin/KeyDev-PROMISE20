from graph import HistoryGraph
from datetime import datetime
import pickle


def run_experiment(experiment_name, dataset_path):
    """
    Run experiment with default parameters and export results into a pickle file.
    First, create a graph for the inital window, then slide that window day by day.
    Find developers, mavens, connectors and jacks for each iteration.
    
    Parameters
    ----------
    experiment_name (str):
        Name of the experiment.

    dataset_path (str):
        Dataset path to read data.
    """

    G = HistoryGraph(dataset_path)

    log_path = "logs/{}.log".format(experiment_name)
    print_log(
        "Started (Total iterations: {}).\n".format(G.get_num_iterations()),
        log_path,
        mode="w",
    )

    # Start iterations
    result = {}
    i = 0
    while True:
        i += 1

        result[G.get_last_included_date()] = {
            "developers": G.get_developers(),
            "jacks": G.get_jacks(),
            "mavens": G.get_mavens(),
            "connectors": G.get_connectors(),
        }

        print_log("{} -> {} nodes\n".format(i, G.get_num_nodes()), log_path)

        if not G.forward_graph_one_day():
            break

    print_log("Ended.\n", log_path)

    with open("results/{}.pkl".format(experiment_name), "wb") as f:
        pickle.dump(result, f)

    print_log("Exported results to 'results/{}.pkl'".format(experiment_name), log_path)


def print_log(info, log_path, mode="a"):
    """
    Print given info along with time string to the file in the `log_path`.
    
    Parameters
    ----------
    info (str):
        Text to log.

    log_path (str):
        Path to log file.

    mode (str):
        'a' (append) or 'write'. 'a' appends to the existing log file.
        'w' overwrites the existing log file.
    """

    assert mode in ["a", "w"], "Log mode can be 'a' (append) or 'w' (write)"

    info = "{}: {}".format(datetime.today(), info)
    with open(log_path, mode) as f:
        f.write(info)
