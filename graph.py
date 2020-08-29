import networkx as nx
import json
import unittest
from itertools import combinations
from data_manager import DataManager, SlidingNotPossible
from collections import defaultdict


class HistoryGraph:
    """
    This class keeps track of changes in a software project. 
    The data must be supplied in "dataset_path".
    
    Attributes
    ----------
    dataset_path (str):
        Path to the dataset which will be used to construct the graph.

    graph_range_in_days (int):
        Number of days included to the artifact graph (i.e. sliding window size).

    distance_limit (float):
        Limit used in file reachability DFS.

    num_files_limit (int):
        Limit for handling the large change sets. The change sets that modify or change 
        files more than this limit are ignored and not added to thr graph.

    score_threshold (float):
        Floating number to consider the scores less than this threshold as zero (0).

    Example Usage
    -------------
    ```
    G = HistoryGraph(dataset_path=<path-to-dataset>)
    
    while True:
        # Do your stuff here

        if not G.forward_graph_one_day():
            break
    ```
    """

    def __init__(
        self,
        dataset_path,
        graph_range_in_days=365,  # Graph range or sliding window size
        distance_limit=10.0,  # Depth limit for DFS
        num_files_limit=50,  # Limit for handling large change sets
        score_threshold=0.000005,  # Lower scores will be ignored
    ):
        """
        Initialize the HistoryGraph object. Look at the class docstring for details.
        """
        self._graph_range_in_days = graph_range_in_days
        self._dataset_path = dataset_path
        self._distance_limit = distance_limit
        self._num_files_limit = num_files_limit
        self._score_threshold = score_threshold
        self._number_of_files_in_project = 0

        # Attribute to keep generated data. Pregenerated data can be used again and
        # again. These have to be deleted while sliding the window.
        self._current_data = {
            "devG": None,
            "dev_to_reachable_files": None,
            "dev_to_rare_files": None,
            "file_to_devs": None,
            "node_kinds": None,
            "jacks": None,
            "mavens": None,
            "connectors": None,
        }

        # Create data manager instance to handle the sliding window approach
        self._data_manager = DataManager(dataset_path, graph_range_in_days)

        # Create the first state of the artifact graph
        self._G = nx.Graph()
        self._initialize_graph()

    def _filter_nodes_by_kind(self, kind, G=None):
        """
        Find the nodes whose kind is `kind`.

        Parameters
        ----------
        kind(str):
            Desired node kind.
            
        G (networkx.Graph):
            Graph to find the kinds of its nodes. If no graph is given, the default 
            is the whole artifact graph.

        Returns
        -------
        list:
            Nodes (strings) whose kind is the given `kind`.
        """
        if G == None:
            G = self._G

        return [node for node, k in G.nodes(data="kind") if k == kind]

    def _initialize_graph(self):
        """
        Initialize the graph with the change sets in the first window.
        """

        change_sets_add = self._data_manager.get_initial_window()

        self._number_of_files_in_project = change_sets_add[-1].num_files_in_project
        self._add_change_sets(change_sets_add)

    def _add_change_sets(self, change_sets):
        """
        Add all nodes and edges for the given change sets.

        Parameters
        ----------
        change_sets (list):
            List of change sets (ChangeSet) to add to the graph.
        """

        if change_sets == []:
            return

        for cs in change_sets:
            files_add_modify = []
            files_delete = []
            files_rename_dict = {}
            for cc in cs.code_changes:
                if cc.change_type == "DELETE":
                    files_delete.append(cc.file_path)
                elif cc.change_type == "RENAME":
                    files_rename_dict[cc.old_file_path] = cc.file_path
                else:
                    files_add_modify.append(cc.file_path)

            # Rename files
            # There is no edge for rename relations, just change the name of the nodes.
            self._rename_nodes(files_rename_dict)

            # Remove nodes for deleted files
            self._remove_nodes(files_delete)

            # Ignore large change sets
            if len(files_add_modify) > self._num_files_limit:
                continue

            # Add new nodes and edges
            self._G.add_node(cs.commit_hash, kind="ChangeSet")
            self._G.add_node(cs.author, kind="Developer")

            # The edges between developers and change set will have zero (0) distance.
            # So, date of these edges will be None.
            self._G.add_edge(cs.author, cs.commit_hash, date=None)

            # Does not affect the existing nodes
            self._G.add_nodes_from(files_add_modify, kind="File")
            self._G.add_edges_from(
                [
                    (cs.commit_hash, filename, {"date": cs.date})
                    for filename in files_add_modify
                ],
                kind="include",
            )

            self._G.add_nodes_from(cs.issues, kind="Issue")
            self._G.add_edges_from(
                [
                    (cs.commit_hash, issue_id, {"date": cs.date})
                    for issue_id in cs.issues
                ],
                kind="link",
            )

    def _remove_change_sets(self, change_sets):
        """
        Remove the given change set nodes and the nodes become unconnected
        after removing the change set nodes.

        Parameters
        ----------
        change_sets (list):
            List of change sets (ChangeSet) to remove from the graph.
        """

        self._remove_nodes([cs.commit_hash for cs in change_sets])

    def _remove_nodes(self, nodes):
        """
        Remove the given nodes. 
        Then, remove the nodes with no edge (i.e. unconnected nodes).

        Parameters
        ----------
        nodes (list):
            List of nodes to remove from the graph.
        """

        if nodes == []:
            return

        self._G.remove_nodes_from(nodes)
        unconnected_nodes = [*nx.isolates(self._G)]
        self._G.remove_nodes_from(unconnected_nodes)

    def _rename_nodes(self, mapping):
        """
        Rename the nodes according to the given mapping.

        Parameters
        ----------
        mapping (dict):
            Dictionary with old and new node name pairs.
        """

        if mapping == {}:
            return

        self._G = nx.relabel_nodes(self._G, mapping)

    def _which_day(self, edge_date):
        """
        Get the number of days passed from the start date of the graph to 
        `edge_date` (including `edge_date`). For example, return 5 if the start
        date of the graph is 24 Nov 2012 and the `edge_date` is 29 Nov 2012.
        
        Parameters
        ----------
        edge_date (datetime.datetime):
            Date to find which day in the graph.

        Returns
        -------
        int:
            Number representing the days passed from to start date of the graph
            until the given date (inclusive).
        """

        first_date_in_graph = self._data_manager.get_first_included_date()

        return (edge_date - first_date_in_graph).days + 1

    def _calculate_distance(self, edge_date):
        """
        Return a distance inversely proportional to recency. (distance = 1 / recency)
        
        Parameters
        ----------
        edge_date (datetime.datetime):
            Date to calculate distance depending on its recency.
        
        Returns
        -------
        float:
            Distance of the edge (distance = 1 / recency).
        """

        # Check if the edge is between a developer and a change set.
        if edge_date == None:
            return 0

        recency = self._which_day(edge_date) / self._graph_range_in_days

        if recency == 0:
            distance = float("inf")
        else:
            distance = 1 / recency

        return distance

    def _find_reachable_files(self, developer):
        """ 
        Return the list of reachable files by the given developer. 
        Starting from the developer node (source node), iterate over edges in a depth
        first search (DFS) manner until reaching the "distance limit" or until reaching
        another developer node. 

        Parameters
        ----------
        developer (str):
            Developer name

        Returns
        -------
        list:
            Files reached by the given developer.
        """

        visited = set([developer])
        node_kinds = self._get_node_kinds()
        reachable_files = []
        stack = [(developer, 0, iter(self._G[developer]))]

        while stack:
            parent, distance_now, children = stack[-1]
            try:
                child = next(children)

                if child in visited:
                    continue

                # If you use a more complicated distance metric, keeping distances
                # calculated before in a dictionary can be faster.
                edge_date = self._G[parent][child]["date"]
                distance_now += self._calculate_distance(edge_date)
                if distance_now > self._distance_limit:
                    continue

                if node_kinds[child] == "Developer":
                    continue

                if node_kinds[child] == "File":
                    reachable_files.append(child)

                visited.add(child)
                stack.append((child, distance_now, iter(self._G[child])))
            except StopIteration:
                stack.pop()

        return reachable_files

    def _calculate_rsrd_distances(self):
        """
        Calculates Reciprocal Sum of Reciprocal Distances (RSRD) for each
        developer pair.

        Returns
        ------
        dict:
            Dictionary for developers pairs and RSRD distance between them. 
            For example, `{(d1,d2): 0.25, (d1,d3): 0.50, (d2,d3): 0.75}` 
        """

        devs = set(self.get_developers())
        dev_pair2distances = defaultdict(list)
        for start in devs:
            other_devs = devs.difference(set([start]))
            paths = nx.all_simple_paths(
                self._G, source=start, target=other_devs, cutoff=4
            )
            for path in paths:
                end = path[-1]
                dev_pair2distances[(start, end)].append(len(path) - 1)

        dev_pair2rsrd = {}
        for start, end in combinations(devs, 2):
            dev_pair = (start, end)
            if dev_pair in dev_pair2distances:
                distances = dev_pair2distances[dev_pair]
                srd = sum(1 / d for d in distances)
                if srd != 0:
                    rsrd = 1 / srd
                    dev_pair2rsrd[dev_pair] = rsrd

        return dev_pair2rsrd

    def _get_node_kinds(self):
        """
        Get node kinds in the artifact graph. Generate the dictionary if it is not
        generated yet. Otherwise return the pregenerated dictionary.

        Returns
        -------
        dict:
            Mapping from the nodes in the artifact graph to their kinds.
        """

        if self._current_data["node_kinds"] == None:
            self._current_data["node_kinds"] = nx.get_node_attributes(self._G, "kind")

        return self._current_data["node_kinds"]

    def _sort_and_filter(self, d):
        """
        Sort by scores in descending order.
        Exclude the ones who have score less than the score threshold.

        Parameters
        ----------
        d (dict):
            Any dictionary.

        Returns
        -------
        dict:
            Sorted and filtered copy of the given dictionary.
        """
        return {
            k: d[k]
            for k in sorted(d, key=lambda x: d[x], reverse=True)
            if d[k] >= self._score_threshold
        }

    def forward_graph_one_day(self):
        """
        Update the graph by removing the components from the first included day
        and adding the components for the day after the last included day.
        
        Returns
        -------
        bool:
            False if sliding is not possible, otherwise return True. 
        """

        # Try to slide the window one day.
        try:
            change_sets_add, change_sets_remove = self._data_manager.forward_one_day()
        except SlidingNotPossible:
            return False

        self._remove_change_sets(change_sets_remove)
        self._add_change_sets(change_sets_add)

        # Update the number of files in the whole project.
        if change_sets_add:
            self._number_of_files_in_project = change_sets_add[-1].num_files_in_project

        # Clear the things related to the previous day.
        for key in self._current_data:
            self._current_data[key] = None
        return True

    def get_file_to_devs(self):
        """
        Get a dictionary for files and developers reached them. 
        
        Generate the dictionary if it is not generated yet. Otherwise return the
        pregenerated dictionary.

        Returns
        -------
        dict:
            Mapping from the files in the artifact graph to the list of developers
            reached them. For example, `{f1:[d1], f2:[d1], f3:[d2], f4:[d1,d2]}`
        """

        if self._current_data["file_to_devs"] == None:
            dev_to_files = self.get_dev_to_reachable_files()
            file_to_devs = defaultdict(list)
            for dev in dev_to_files:
                reachable_files = dev_to_files[dev]
                for f in reachable_files:
                    file_to_devs[f].append(dev)

            self._current_data["file_to_devs"] = file_to_devs

        return self._current_data["file_to_devs"]

    def get_dev_to_reachable_files(self):
        """
        Get a dictionary for developers and the reachable files by them. For each
        developer run a DFS to find reachable files.
        
        Generate the dictionary if it is not generated yet. Otherwise return the
        pregenerated dictionary.

        Returns
        -------
        dict:
            Mapping from the developers in the artifact graph to the files reached
            by them. For example, `{d1:[f1, f2, f4], d2:[f3, f4]}`
        """

        if self._current_data["dev_to_reachable_files"] == None:
            dev_to_reachable_files = {}
            for dev in self.get_developers():
                dev_to_reachable_files[dev] = self._find_reachable_files(dev)
            self._current_data["dev_to_reachable_files"] = dev_to_reachable_files

        return self._current_data["dev_to_reachable_files"]

    def get_dev_to_rare_files(self):
        """
        Get a dictionary for developers and their rarely reached files.

        Generate the dictionary if it is not generated yet. Otherwise return the
        pregenerated dictionary.

        Returns
        -------
        dict:
            Mapping from the developers in the artifact graph to the rarely reached
            files reached by them. For example, `{d1:[f1, f2], d2:[f3]}` 
        """

        if self._current_data["dev_to_rare_files"] == None:
            file_to_devs = self.get_file_to_devs()

            dev_to_rarefiles = defaultdict(list)
            for f in file_to_devs:
                devs = file_to_devs[f]
                if len(devs) == 1:
                    dev = devs[0]
                    dev_to_rarefiles[dev].append(f)

            self._current_data["dev_to_rare_files"] = dev_to_rarefiles

        return self._current_data["dev_to_rare_files"]

    def get_developer_graph(self):
        """
        Get the developer graph where developers are the nodes and distances are the
        edges. If distance is 0 between 2 developers, then there is no edge between
        them.

        Generate the developer graph if it is not generated yet. Otherwise return the
        pregenerated developer graph.

        Returns
        -------
        networkx.Graph:
            Graph with nodes for developers and edges for RSRD values between them.
        """

        if self._current_data["devG"] == None:
            dev_pair2distances = self._calculate_rsrd_distances()
            edge_list = [
                (dev1, dev2, {"distance": float(distance)})
                for (dev1, dev2), distance in dev_pair2distances.items()
                if float(distance) > 0
            ]
            devG = nx.Graph()
            devG.add_edges_from(edge_list)

            self._current_data["devG"] = devG

        return self._current_data["devG"]

    def get_developers(self):
        """
        Get the list of developers in the current artifact graph.

        Returns
        -------
        list:
            Developers (string) in the artifact graph.
        """

        return self._filter_nodes_by_kind("Developer")

    def get_files(self):
        """
        Get the list of files in the current artifact graph.

        Returns
        -------
        list:
            Files (string) in the artifact graph.
        """

        return self._filter_nodes_by_kind("File")

    def get_num_files(self):
        """
        Get the number of files in the project, not just in the graph.

        Returns
        -------
        int:
            Number of files in the project, not just in the graph.
        """

        return self._number_of_files_in_project

    def get_num_iterations(self):
        """
        Get the number of possible iterations in the sliding window approach.
        In other words, get the number of days possible to identify jack, mavens etc.
        This also counts the initial position of the sliding window (i.e. inclusive).

        Returns
        -------
        int:
            Number of possible iterations.
        """

        return self._data_manager.get_num_possible_iterations()

    def get_num_nodes(self):
        """
        Get the number of nodes in the current artifact graph. 

        Returns
        -------
        int:
            Number of nodes in the current artifact graph. 
        """
        return self._G.number_of_nodes()

    def get_num_rare_files(self):
        """
        Get the number of rarely reached files.

        Returns
        -------
        int:
            Number of rarely reached files.
        """

        dev_to_rare_files = self.get_dev_to_rare_files()
        return sum(len(files) for files in dev_to_rare_files.values())

    def get_last_included_date(self):
        """
        Get the last date included to the current artifact graph.

        Returns
        -------
        datetime.datetime:
            Date lastly included to the current artifact graph.
        """
        return self._data_manager.get_last_included_date()

    #
    # JACK
    #

    def get_jacks(self):
        """
        Get a dictionary for the jacks and their file coverage scores. The developers
        whose scores are less than the score threshold are ignored and removed from the
        dictionary.

        Generate the dictionary if it is not generated yet. Otherwise return the
        pregenerated dictionary.

        Returns
        -------
        dict:
            A sorted (by file coverage) dictionary for the developers and 
            their file coverage scores.
        """

        if self._current_data["jacks"] == None:
            dev_to_files = self.get_dev_to_reachable_files()
            len_files = self.get_num_files()
            dev_to_file_coverage = {}
            for dev, reachable_files in dev_to_files.items():
                dev_to_file_coverage[dev] = len(reachable_files) / len_files

            self._current_data["jacks"] = self._sort_and_filter(dev_to_file_coverage)

        return self._current_data["jacks"]

    #
    # MAVEN
    #

    def get_mavens(self):
        """
        Get a dictionary for the developers and their mavenness scores. The developers
        whose scores are less than the score threshold are ignored and removed from
        the dictionary.
        
        Generate the dictionary if it is not generated yet. Otherwise return the
        pregenerated dictionary.

        Returns
        -------
        dict:
            A sorted (by mavenness score) dictionary for the developers and 
            their mavenness scores.
        """
        if self._current_data["mavens"] == None:
            dev_to_rare_files = self.get_dev_to_rare_files()
            num_rare_files = self.get_num_rare_files()
            dev_to_mavenness = {}
            for dev, rare_files in dev_to_rare_files.items():
                dev_to_mavenness[dev] = len(rare_files) / num_rare_files

            self._current_data["mavens"] = self._sort_and_filter(dev_to_mavenness)

        return self._current_data["mavens"]

    #
    # CONNECTOR
    #

    def get_connectors(self):
        """
        Get a dictionary for the developers and their betweenness centrality in
        developer graph. The developers whose scores are less than the score
        threshold are ignoredand removed from the dictionary. 
        
        Generate the dictionary if it is not generated yet. Otherwise return the
        pregenerated dictionary.

        Returns
        -------
        dict:
            Sorted (by betweenness centrality) dictionary for the developers and 
            their betweenness centrality in the developer graph.
        """
        if self._current_data["connectors"] == None:
            devG = self.get_developer_graph()
            dev_to_betweenness = nx.betweenness_centrality(
                devG, weight="distance", normalized=True
            )

            self._current_data["connectors"] = self._sort_and_filter(dev_to_betweenness)

        return self._current_data["connectors"]


class TestHistoryGraph(unittest.TestCase):
    @staticmethod
    def compare(d1, d2):
        """
        Compare the given dictinaries
        Ignore the orders for lists.
        """

        def compare_dicts(d1_, d2_):
            if d1_ == {} and d2_ == {}:
                return True

            for key in d1_:
                if key not in d2_:
                    return False

                if type(d1_[key]) == dict:
                    if not compare_dicts(d1_[key], d2_[key]):
                        return False
                elif type(d1_[key]) == list:
                    if not compare_lists(d1_[key], d2_[key]):
                        return False
                else:
                    if not d1_[key] == d2_[key]:
                        return False

            return True

        def compare_lists(l1_, l2_):
            from collections import Counter

            return Counter(l1_) == Counter(l2_)

        return compare_dicts(d1, d2)

    def test_reachable_files(self):
        G = HistoryGraph(
            "data/test_data/sample_graph.json",
            graph_range_in_days=300,
            distance_limit=10,
        )
        i = 1
        result = {}
        while True:
            dev_to_files = G.get_dev_to_reachable_files()
            files = G.get_files()
            result[str(i)] = {"dev_to_files": dev_to_files, "files": files}
            i += 1
            if not G.forward_graph_one_day():
                break

        with open("data/test_data/sample_reachable_files.json", "r") as f:
            sample_result = json.load(f)
        assert TestHistoryGraph.compare(result, sample_result), "Wrong result"

    def test_mavens(self):
        G = HistoryGraph(
            "data/test_data/sample_graph.json",
            graph_range_in_days=300,
            distance_limit=10,
        )
        i = 1
        result = {}
        while True:
            mavens = G.get_mavens()
            result[str(i)] = mavens
            i += 1
            if not G.forward_graph_one_day():
                break

        with open("data/test_data/sample_mavens.json", "r") as f:
            sample_result = json.load(f)

        assert TestHistoryGraph.compare(result, sample_result), "Wrong result"

    def test_connectors(self):
        G = HistoryGraph(
            "data/test_data/sample_graph.json",
            graph_range_in_days=300,
            distance_limit=10,
        )
        i = 1
        result = {}
        while True:
            connectors = G.get_connectors()
            result[str(i)] = connectors
            i += 1
            if not G.forward_graph_one_day():
                break

        with open("data/test_data/sample_connectors.json", "r") as f:
            sample_result = json.load(f)

        assert TestHistoryGraph.compare(result, sample_result), "Wrong result"

    def test_jacks(self):
        G = HistoryGraph(
            "data/test_data/sample_graph.json",
            graph_range_in_days=300,
            distance_limit=10,
        )
        i = 1
        result = {}
        while True:
            jacks = G.get_jacks()
            result[str(i)] = jacks
            i += 1
            if not G.forward_graph_one_day():
                break

        with open("data/test_data/sample_jacks.json", "r") as f:
            sample_result = json.load(f)

        assert TestHistoryGraph.compare(result, sample_result), "Wrong result"


if __name__ == "__main__":
    unittest.main()
