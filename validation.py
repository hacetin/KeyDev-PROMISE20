import pickle
import random
from extract_commenters import generate_date_to_top_commenters
from collections import defaultdict

random.seed(2020)


def accuracy(set1, set2):
    """
    Calculate intersection ratio of set1 and set2 over set1. 
    For example, return 0.75 if "set1={1,2,3,4}" and "set2={1,2,3,5,6,7}"

    Parameters
    set1 (set):
        Set of items.

    set2 (set):
        Set of items.

    Returns
    -------
    float:
        Intersection ratio of set1 and set2 over set1.
    """

    return len(set1.intersection(set2)) / len(set1)


def print_table(table):
    """
    Prints topk accuracy table in a human readable way.

    Parameters
    ----------
    table (dict):
        Mapping from row and column indexes to the values of the cells.
        For example, "{(0,0): 0.65,  (0,1): 0.78}"
    """

    rows = sorted(set(i for i, _ in table))
    cols = sorted(set(j for _, j in table))

    print("\t" + "\t".join(str(x) for x in cols))
    for i in rows:
        row_text = str(i)
        for j in cols:
            if (i, j) in table:
                row_text += "\t{:.2f}".format(table[(i, j)] * 100)
            else:
                row_text += "\t-"
        print(row_text)


def topk_table(date_to_predicted_key_developers, date_to_correct_key_developers):
    """
    Calculate accuracies which are required for topk table.

    Parameters
    ----------
    date_to_predicted_key_developers (dict):
        Mapping from dates to list of predicted key developers.

    date_to_correct_key_developers (dict):
        Mapping from dates to list of correct (true) key developers (like ground truth).

    Returns
    -------
    dict:
        Mapping from row and column indexes to the values of the cells.
        For example, "{(0,0): 0.65,  (0,1): 0.78}"
    """

    kvalues = [1, 3, 5, 10]
    accs = {(k1, k2): [] for k1 in kvalues for k2 in kvalues if k1 <= k2}
    for date, key_developers in date_to_predicted_key_developers.items():
        top_commenters = list(date_to_correct_key_developers[date])

        for k1, k2 in accs:
            acc = accuracy(set(top_commenters[:k1]), set(key_developers[:k2]))
            accs[(k1, k2)].append(acc)

    avg_accs = {c: sum(values) / len(values) for c, values in accs.items()}
    return avg_accs


def generate_date_to_intersection(date_to_results):
    """
    Generate a mapping from date to intersection developers that date.

    Parameters
    ----------
    date_to_results (dict):
        Mapping from date to results. Results have to include "jacks" "mavens"
        and "connectors" categories at the same time.

    Returns
    -------
    dict: 
        Mapping from date to intersection developers that date.
    """

    date_to_intersection = {}
    for date, results in date_to_results.items():
        intersection_developers = set.intersection(
            set(results["jacks"].keys()),
            set(results["mavens"].keys()),
            set(results["connectors"].keys()),
        )

        # Let's sort the intersection developers according to jack score
        # Jacks are already sorted
        sorted_intersection_developers = {
            dev: score
            for dev, score in results["jacks"].items()
            if dev in intersection_developers
        }
        date_to_intersection[date] = sorted_intersection_developers

    return date_to_intersection


def validation(date_to_key_developers, date_to_top_commenters, date_to_developers):
    """
    Perform validation by considering the top commenters as the ground truth (actually,
    it is a pseudo ground truth). Also, perform Monte Carlo simulation. 

    Then, print a topk accuracy table for the given key developers and another topk 
    accuracy table for monte carlo simulation.

    Parameters
    ----------
    date_to_key_developers (dict):
        Mapping from dates to key developers (one type of key developer such as "jacks"
        or "intersection") in the sliding window ending that date.

    date_to_top_commenters (dict):
        Mapping from dates to top commenters in the sliding window ending that date.
        
    date_to_developers (dict):
        Mapping from dates to all developers in the sliding window ending that date.
    """
    kvalues = [1, 3, 5, 10]

    ## OUR APPROACH
    print("Our Approach - Top Commenters")
    acc_table = topk_table(date_to_key_developers, date_to_top_commenters)

    print_table(acc_table)

    ## MONTE CARLO SIMULATION
    print("Monte Carlo Simulation - Top Commenters")
    num_simulations = 1000
    monte_carlo_acc_tables = []
    for _ in range(num_simulations):
        # Generate random key developers
        date_to_random_developers = {}
        for date, key_developers in date_to_key_developers.items():
            random_developers = random.sample(
                date_to_developers[date], len(key_developers)
            )
            date_to_random_developers[date] = random_developers

        acc_table = topk_table(date_to_random_developers, date_to_top_commenters)
        monte_carlo_acc_tables.append(acc_table)

    # Find the average accuracy of all simulations

    # First, find the sum of the accuracies for each table cell
    monte_carlo_sum_acc_table = defaultdict(lambda: 0)
    for acc_table in monte_carlo_acc_tables:
        for cell, score in acc_table.items():
            monte_carlo_sum_acc_table[cell] += score

    # Then, divide the sums to number of simulations to find average of the accuracies
    # for each table cell
    monte_carlo_avg_acc_table = {
        k: v / num_simulations for k, v in monte_carlo_sum_acc_table.items()
    }

    print_table(monte_carlo_avg_acc_table)


if __name__ == "__main__":
    for project_name in ["hadoop", "hive", "pig"]:
        print("\n\n*****************", project_name.upper(), "*****************")

        print("Reading experiment results.")
        with open("results/{}_dl10_nfl50_sws365.pkl".format(project_name), "rb") as f:
            date_to_results = pickle.load(f)

        # Add intersection to results
        date_to_intersection = generate_date_to_intersection(date_to_results)
        for date in date_to_results:
            date_to_results[date]["intersection"] = date_to_intersection[date]

        print("Extracting comment counts.")
        date_to_top_commenters = generate_date_to_top_commenters(project_name)
        date_to_top_commenters = {
            date: list(top_commenters.keys())
            for date, top_commenters in date_to_top_commenters.items()
        }

        for category in ["jacks", "intersection"]:
            print("\n", "-->", category.upper())
            date_to_developers = {
                date: results["developers"] for date, results in date_to_results.items()
            }
            date_to_key_developers = {
                date: list(results[category].keys())
                for date, results in date_to_results.items()
            }

            validation(
                date_to_key_developers, date_to_top_commenters, date_to_developers
            )

