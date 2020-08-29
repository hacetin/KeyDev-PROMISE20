from datetime import datetime, timedelta
import json
from util import str_to_date, max_of_day, sort_dict
import unittest
from collections import defaultdict


class SlidingNotPossible(Exception):
    """Dummy exception class to raise when there is no more data to slide the window."""

    pass


class CodeChange:
    """
    The class to represent code changes as an object. 

    Attributes
    ----------
    file_path (str):
        Path of the file changed.

    change_type (str):
        Type of the change. It can be ADD, DELETE, MODIFY or RENAME.

    old_file_path (str, default=None):
        Old path of the file changed for RENAME type of changes. If the `change_type` is
        RENAME, the old path of the changed file have to be provided.
    """

    __slots__ = ["file_path", "change_type", "old_file_path"]

    def __init__(self, file_path, change_type, old_file_path=None):

        assert change_type in [
            "ADD",
            "DELETE",
            "MODIFY",
            "RENAME",
        ], "Change type can be ADD, DELETE, MODIFY or RENAME"

        if change_type == "RENAME":
            assert (
                old_file_path != None
            ), "If change type is RENAME, old file path cannot be None"
        else:
            assert (
                old_file_path == None
            ), "If change type is not RENAME, old file path have to be None"

        self.file_path = file_path
        self.change_type = change_type
        self.old_file_path = old_file_path

    def __eq__(self, other):
        return (
            self.file_path == other.file_path
            and self.change_type == other.change_type
            and self.old_file_path == other.old_file_path
        )


class ChangeSet:
    """
    The class to represent change sets as an object. 

    Attributes
    ----------
    commit_hash (str):
        Commit hash of the changeset, in other words the id of it.

    author (str):
        Author of the change set.

    date (datetime.datetime):
        Date and time of when the change set is committed.

    issues (list):
        Issues realted to the change set.

    code_changes (list):
        Code changes in the change set. Code changes should be CodeChange objects.

    num_current_files (int):
        Number of existing files in the whole project.
    """

    __slots__ = [
        "commit_hash",
        "author",
        "date",
        "issues",
        "code_changes",
        "num_files_in_project",
    ]

    def __init__(
        self, commit_hash, author, date, issues, code_changes, num_files_in_project
    ):

        assert (
            type(code_changes) == list
            and code_changes != []
            and type(code_changes[0]) == CodeChange
        ), "'code_changes' have to be a list of 'CodeChange's, and it cannot be empty."

        self.commit_hash = commit_hash
        self.author = author
        self.date = date
        self.issues = issues
        self.code_changes = code_changes
        self.num_files_in_project = num_files_in_project

    def __eq__(self, other):
        return (
            self.commit_hash == other.commit_hash
            and self.author == other.author
            and self.date == other.date
            and self.issues == other.issues
            and self.code_changes == other.code_changes
            and self.num_files_in_project == other.num_files_in_project
        )


class DataManager:
    """
    The class to handle data related issues while using sliding window approach.
    
    Attributes
    ----------
    dataset_path (str):
        Path of the dataset to read.

    sliding_window_size (int):
        Size (range) of the sliding window in days. 
    """

    def __init__(self, dataset_path, sliding_window_size):
        """
        Initialize the DataManager object. Look at the class docstring for details.
        """

        self._dataset_path = dataset_path
        self._sliding_window_size = sliding_window_size
        self._date_to_change_sets = self._generate_date_to_change_sets()
        self._first_date = None  # First included date
        self._last_date = None  # Last included date

    def _generate_date_to_change_sets(self):
        """
        Generate a dictionary for the pairs of date and change sets committed that date.

        Returns
        -------
        dict:
            A sorted (by date) dictionary for date and change sets pairs.
        """

        with open(self._dataset_path, encoding="utf8") as f:
            change_set_jsons = json.load(f)["change_sets"]

        date_to_change_sets = defaultdict(list)
        for change_set_json in change_set_jsons:
            code_changes = []
            for code_change in change_set_json["code_changes"]:
                cc = CodeChange(
                    code_change["file_path"],
                    code_change["change_type"],
                    code_change.get("old_file_path", None),
                )
                code_changes.append(cc)

            change_set = ChangeSet(
                change_set_json["commit_hash"],
                change_set_json["author"],
                max_of_day(str_to_date(change_set_json["date"])),
                change_set_json["issues"],
                code_changes,
                change_set_json["num_current_files"],
            )

            date_to_change_sets[change_set.date].append(change_set)

        # Fill the blanks with empty lists
        dates = list(date_to_change_sets)
        last_date = dates[-1]
        date = dates[0]

        while date < last_date:
            date_to_change_sets[date]
            date += timedelta(days=1)

        return sort_dict(date_to_change_sets)

    def get_num_possible_iterations(self):
        """
        Get the number of possible iterations.

        Returns
        -------
        int:
            Number of possible iterations.
        """
        return len(self._date_to_change_sets) - self._sliding_window_size + 1

    def get_first_included_date(self):
        """
        Get the first included date to the sliding window.

        Returns
        -------
        datetime.datetime:
            First included date to the sliding window.
        """

        return self._first_date

    def get_last_included_date(self):
        """
        Get the last included date to the sliding window.

        Returns
        -------
        datetime.datetime:
            Last included date to the sliding window.
        """

        return self._last_date

    def get_initial_window(self):
        """
        Generate the first sliding window. The date range in the data have to be enough
        to create the window with the given sliding window size.

        Returns
        -------
        list:
            Change sets (sorted by date in ascending order) that the first sliding
            window include.
        """

        self._first_date = list(self._date_to_change_sets)[0]
        self._last_date = self._first_date + timedelta(
            days=self._sliding_window_size - 1
        )

        assert self._last_date in self._date_to_change_sets, (
            "Not enough data to create the first window. The date range in the data "
            "is less than the size of the sliding window"
        )

        change_sets = []
        for date in self._date_to_change_sets:
            if date > self._last_date:
                break

            change_sets.extend(self._date_to_change_sets[date])

        return change_sets

    def can_slide(self):
        """
        Check if sliding the window one more day is possible or not.
        
        Returns
        -------
        bool:
            True if sliding one more date is possible, otherwise False.
        """

        return self._last_date + timedelta(days=1) in self._date_to_change_sets

    def forward_one_day(self):
        """
        Slide the window one day forward.

        Raises
        ------
        SlidingNotPossible:
            If there no more data to slide the window.

        Returns
        -------
        tuple:
            A tuple of 2 lists, which are change sets to add and change sets to remove.
        """

        if not self.can_slide():
            raise SlidingNotPossible(
                "Not enough data to slide window one more day. Last included date is {}".format(
                    self._last_date
                )
            )

        change_sets_remove = self._date_to_change_sets[self._first_date]
        self._first_date += timedelta(days=1)

        self._last_date += timedelta(days=1)
        change_sets_add = self._date_to_change_sets[self._last_date]

        return change_sets_add, change_sets_remove


class TestDataManager(unittest.TestCase):
    def test_initial_window(self):
        data_manager = DataManager("data/test_data/sample_graph.json", 300)
        change_sets = data_manager.get_initial_window()

        assert (
            max_of_day(datetime(2018, 11, 17)) == data_manager.get_first_included_date()
        ), "Sample graph starts on 17 Nov 2018, not on {}".format(
            data_manager.get_first_included_date()
        )

        assert (
            max_of_day(datetime(2019, 9, 12)) == data_manager.get_last_included_date()
        ), "Sample graph's initial window ends on 12 Sep 2019, not on {}".format(
            data_manager.get_first_included_date()
        )

        expected_change_sets = [
            ChangeSet(
                commit_hash="CS0",
                date=max_of_day(str_to_date("2018-11-17T12:00:00Z")),
                author="d1",
                issues=["I0"],
                code_changes=[CodeChange("F0", "ADD")],
                num_files_in_project=1,
            ),
            ChangeSet(
                commit_hash="CS1",
                date=max_of_day(str_to_date("2019-01-15T12:00:00Z")),
                author="d1",
                issues=["I1"],
                code_changes=[CodeChange("F1", "ADD"), CodeChange("F2", "ADD")],
                num_files_in_project=3,
            ),
            ChangeSet(
                commit_hash="CS2",
                date=max_of_day(str_to_date("2019-02-14T12:00:00Z")),
                author="d2",
                issues=["I2"],
                code_changes=[CodeChange("F2", "MODIFY"), CodeChange("F3", "ADD")],
                num_files_in_project=4,
            ),
            ChangeSet(
                commit_hash="CS3",
                date=max_of_day(str_to_date("2019-05-15T12:00:00Z")),
                author="d3",
                issues=["I2"],
                code_changes=[CodeChange("F4", "ADD")],
                num_files_in_project=5,
            ),
        ]

        assert change_sets == expected_change_sets, "Change sets are not as expected"

    def test_sliding_dates(self):
        data_manager = DataManager("data/test_data/sample_graph.json", 300)
        change_sets = data_manager.get_initial_window()
        first_included_date = data_manager.get_first_included_date()
        last_included_date = data_manager.get_last_included_date()
        while True:
            try:
                data_manager.forward_one_day()

                first_included_date += timedelta(days=1)
                assert first_included_date == data_manager.get_first_included_date()

                last_included_date += timedelta(days=1)
                assert last_included_date == data_manager.get_last_included_date()
            except SlidingNotPossible:
                break

    def test_num_possible_iterations(self):
        data_manager = DataManager("data/test_data/sample_graph.json", 300)
        data_manager.get_initial_window()

        assert data_manager.get_num_possible_iterations() == 61


if __name__ == "__main__":
    unittest.main()
