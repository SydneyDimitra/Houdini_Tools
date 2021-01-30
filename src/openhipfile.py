import logging
import os
import re

import humanize
import pendulum

from PyQt4 import (QtCore, QtGui)

# Temporary to help test in and out of houdini
HOUDINI = False

if HOUDINI:
    import hou
    # Initialise the LOG object
    LOG = logging.getLogger("dnhou.{0}".format(__name__))
else:
    # Initialise the LOG object
    LOG = logging.getLogger("simple example")
    LOG.setLevel(logging.INFO)


class PathTreeItem(object):
    """The path TreeItem class. """
    def __init__(self, file_path, file_name=None, parent=None):
        """Construct a PathTreeItem object.

        Args:
            file_path (str): The full path of the file.
            file_name (str): The name of the file.
            parent (PathTreeItem): The parent tree item.
        """
        self.file_path = file_path
        self._file_name = file_name or os.path.basename(file_path)
        self._parent = parent

        self._children = []
        self._contents = None
        self._is_loaded = False

    @property
    def name(self):
        return self._file_name

    @property
    def children(self):
        return self._children

    @property
    def has_children(self):
        if self._contents is None:
            self.get_contents()
        return True if self._contents else False

    @property
    def contents(self):
        if self._contents is None:
            self.get_contents()
        return self._contents

    @property
    def is_loaded(self):
        return self._is_loaded

    def set_loaded(self, loaded):
        """Set is_loaded property.

        Args:
            loaded (bool): Boolean input to set the property
        """
        self._is_loaded = loaded

    def get_contents(self):
        self._contents = get_contents(self.file_path)

    def data(self, column, role=QtCore.Qt.DisplayRole):
        """Get data for each item, column and role.
        Args:
            column (int): Column number.
            role (QtCore.Qt.ItemDataRole): The item data role.
        """
        if role == QtCore.Qt.DisplayRole:
            return OUTLINER_COLUMN_ORDER[column]
        return None

    def child(self, row):
        """Returns the child that corresponds to the specified row number
        in the items list of child items.
        
        Args:
            row (int): The row number.
        """
        if (row < 0 or row >= len(self._children)):
            return None
        return self._children[row]

    def childCount(self):
        """Return the number of child items held."""
        return len(self._children)

    def columnCount(self):
        return len(OUTLINER_COLUMN_ORDER)

    def row(self):
        """Return the items location within its parents list of items."""
        if self._parent:
            return self._parent.children.index(self)
        return -1

    def parentItem(self):
        return self._parent

    def appendChild(self, child):
        self._children.append(child)


class FolderItem(PathTreeItem):
    """This class represents a folder tree item."""

    def data(self, column, role=QtCore.Qt.DisplayRole):
        """Get data for each item, column and role.
        Args:
            column (int): Column number.
            role (QtCore.Qt.ItemDataRole): The item data role.
        """
        # Colouring the extra folders under the user folder for better
        # visibility (these include automated saved scene files that might
        # be handy)
        if column == 0:
            if role == QtCore.Qt.DisplayRole:
                return self.name
            elif role == QtCore.Qt.ForegroundRole:
                if self.name.lower() in ["backup", "render"]:
                    return QtGui.QColor(255, 255, 52)
        return None


class FileGroupItem(PathTreeItem):
    """This class represents a file group tree item."""

    def __init__(self, file_path, parent=None):
        """Construct FileGroupItem object.

        Args:
            file_path (str): Full path of file.
            parent (PathTreeItem): The parent tree item.
        """
        super(FileGroupItem, self).__init__(file_path, parent=parent)
        self.latest = None

    def _get_latest(self):
        """Get latest file in the file.

        Returns:
            type or None: The latest child file path.
        """
        if not self.children:
            return None

        return sorted(
            self.children, key=lambda item: item.creation_date, reverse=True
        )[0]

    def data(self, column, role=QtCore.Qt.DisplayRole):
        """Get data for each item, column and role.
        Args:
            column (int): Column number.
            role (QtCore.Qt.ItemDataRole): The item data role.
        """
        self.latest = self._get_latest()
        data = None

        if role == QtCore.Qt.DisplayRole:
            column_data = [
                self.name,
                self.latest.name,
                self.latest.time,
                self.latest.size
            ]
            try:
                data = column_data[column]
            except IndexError:
                pass
        return data


class FileItem(PathTreeItem):
    """This class represents a file tree item."""

    def __init__(self, file_path, parent=None):
        """Construct FileItem object.

        Args:
            file_path (str): Full path of file.
            parent (PathTreeItem): The parent tree item.
        """
        super(FileItem, self).__init__(file_path, parent=parent)
        self.date = None
        self.time = None
        self.size = self._get_file_size()
        self._evaluate_creation_date()

    def data(self, column, role=QtCore.Qt.DisplayRole):
        """Get data for each item, column and role.
        Args:
            column (int): Column number.
            role (QtCore.Qt.ItemDataRole): The type of data queried.
        """
        if role == QtCore.Qt.DisplayRole:
            if column == 0:
                return self.name
            if column == 2:
                return self.time
            if column == 3:
                return self.size
        elif role == QtCore.Qt.ForegroundRole and column == 0:
            return QtGui.QColor(46, 187, 209)
        return None

    @property
    def creation_date(self):
        """Return the creation date object of the file."""
        return self.date

    def _evaluate_creation_date(self):
        """Get the date of creation of the file:
        Time is the user friendly string for the UI Column
        Date is the date object for comparison of the versions's age.
        """
        creation_time = os.stat(self.file_path).st_ctime
        self.date = pendulum.from_timestamp(creation_time)
        self.time = self.date.strftime("%Y-%m-%d %H:%M:%S")

    def _get_file_size(self):
        """Get the size of the file of given path.

        Returns:
            (str): file size in readable form
        """
        file_size = os.stat(self.file_path).st_size
        return humanize.naturalsize(file_size, binary=True)


class TreeModel(QtCore.QAbstractItemModel):
    """The Tree Model Class."""
    def __init__(self):
        """Construct TreeModel object."""
        super(TreeModel, self).__init__()
        self._rootItem = PathTreeItem("root", parent=None)
        self._items = {}

        self.loadTree()

    def data(self, index, role):
        """Get data for each item, column and role.
        Args:
            index (QModelIndex): The item's index.
            role (QtCore.Qt.ItemDataRole): The type of data queried.
        """
        if not index.isValid():
            return QtCore.QVariant()

        item = index.internalPointer()

        return item.data(index.column(), role)

    def flags(self, index):
        """Set the required flags for each item on the model.
        Args:
            index (QModelIndex): The item index.
        """
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        """Return the data that we stored on the root item.
        Args:
            section ():
            orientation (): 
            role (QtCore.Qt.ItemDataRole): The item data role.
        """
        if (orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole):
            return self._rootItem.data(section)
        return QtCore.QVariant()

    def index(self, row, column, parent):
        """Get item's index.
        Args:
            row ():
            column ():
            parent (PathTreeItem): The parent tree item.
        """
        # if not hasIndex(row, column, parent):
        #     return QtQui.QModelIndex()

        parentItem = None
        if not parent.isValid():
            parentItem = self._rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        return QtCore.QModelIndex()

    def parent(self, index):
        """
        Args:
            index (QModelIndex): The index of item.
        """
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parentItem()

        if parentItem == self._rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        """Return the number of child items for the PathTreeItem that corresponds
        to a given model index, or the number of top-level items if an invalid
        index is specified.
        Args:
            parent (PathTreeItem): The parent tree item.
        """
        parentItem = None
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self._rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        return self._rootItem.columnCount()

    def loadTree(self):
        rootpaths = get_folder_paths()
        for path in rootpaths:
            self._items[path] = FolderItem(path, parent=self._rootItem)
            self._rootItem.appendChild(self._items[path])
            #self.load_children(self._items[path])

    def load_children(self, item):
        #  Iterate over the files, creating a model item for each one.
        if item.is_loaded:
            return
        row = 0
        child_dir_paths, file_groups, independent_files = item.contents

        for group_path in sorted(file_groups.keys()):
            file_paths = file_groups[group_path]
            group_item = FileGroupItem(group_path, parent=item)
            self._items[group_path] = group_item

            item.appendChild(group_item)

            for file_path in file_paths:
                file_item = FileItem(file_path, parent=group_item)
                self._items[file_path] = file_item
                group_item.appendChild(file_item)

            row += 1

        for file_path in independent_files:
            file_item = FileItem(file_path, parent=item)
            self._items[file_path] = file_item
            item.appendChild(file_item)

        for folder_path in sorted(child_dir_paths):
            # Create folder items:
            folder_item = FolderItem(folder_path, parent=item)
            self._items[folder_path] = folder_item
            item.appendChild(folder_item)

        item.set_loaded(True)

    def hasChildren(self, index):
        if not index.isValid():
            return True
        item = index.internalPointer()

        return item.has_children or item.childCount() > 0

    def canFetchMore(self, index):
        if not index.isValid():
            return False
        item = index.internalPointer()
        return item.has_children

    def fetchMore(self, index):
        item = index.internalPointer()

        if item.has_children:
            self.load_children(item)


class TreeView(QtGui.QTreeView):
    def __init__(self):
        """Construct TreeView object."""
        super(TreeView, self).__init__()
        self.setHeader(_ColumnHeaderView(parent=self))

    def setModel(self, model):
        super(TreeView, self).setModel(model)
        self.header().reset_column_sizes()

# Define column names and sizes as globals
OUTLINER_COLUMN_ORDER = ["Name", "Latest", "Time", "Size"]
OUTLINER_COLUMN_WIDTHS = {"Name": 300, "Latest": 300, "Time": 200, "Size": 200}


class _ColumnHeaderView(QtGui.QHeaderView):
    def __init__(self, parent=None):
        """Construct _ColumnHeaderView object."""      
        super(_ColumnHeaderView, self).__init__(
            QtCore.Qt.Horizontal,
            parent=parent
        )

        self.setStretchLastSection(True)

    def reset_column_sizes(self):
        """ Reset the columns to the default sizes."""
        for column_index, column_name in enumerate(OUTLINER_COLUMN_ORDER):
            self.resizeSection(
                column_index,
                OUTLINER_COLUMN_WIDTHS[column_name]
            )
            self.showSection(column_index)
            #self.setSectionResizeMode(column_index, self.Stretch)


def get_folder_paths():
    """Find Houdini and User directory paths.
    Returns:
        paths (list(str)): Full directory paths.
    """
    # Hardcode the paths for now
    houdini_path = "/user_data/hou"
    user_data_path = "/user_data/examples"
    # Check if the paths exist.
    paths = []
    if os.path.isdir(houdini_path):
        paths.append(houdini_path)
    if os.path.isdir(user_data_path):
        paths.append(user_data_path)
    return paths


def get_contents(directory):
    """Get contents for each directory.

    Returns:
        child_dir_paths (list(str)): The list of child paths that are directories.
        file_groups (list(str)): The list of file groups.
        independent_files (list(str)): The list of the independent files.
    """
    if os.path.isfile(directory):
        return ()
    if not os.path.exists(directory):
        return ()
    contents = os.listdir(directory)
    if not contents:
        return ()

    child_file_paths = []
    child_dir_paths = []

    for name in contents:
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            child_file_paths.append(path)
        else:
            child_dir_paths.append(path)

    file_groups, independent_files = _get_file_groups(child_file_paths)

    return child_dir_paths, file_groups, independent_files


def _get_file_groups(file_paths):
    """Group the different versions of the hip files.

    Args:
        file_paths (list(str)): List of the full file paths.

    Returns:
        tuple: (file_groups (dict), independent_files(list))
            Dictionary maping the group name to a group of
            file paths.
            List of independent files that don't follow the version format,
            and therefore don't create groups.
    """
    file_groups = {}
    independent_files = []
    pattern = "(?P<group_name>.*)_v[0-9]{3}.*hip"

    for file_path in file_paths:
        file_dir, file_name = os.path.split(file_path)
        match = re.match(pattern, file_name)
        if match:
            file_groups.setdefault(
                os.path.join(file_dir, match.group("group_name")), []
            ).append(file_path)
        elif file_path.endswith(".hip"):
            independent_files.append(file_path)
    independent_files = sorted(independent_files)
    for key, values in file_groups.iteritems():
        file_groups[key] = sorted(values)
    return file_groups, independent_files


class OpenHipFile(QtGui.QDialog):
    """This class represents a QtGui QDialog object."""
    def __init__(self, parent=None):
        """Construct dnHipOpen object.

        Create a custom Dialog box, based on the class QtGui.QDialog, adding
        adds some extra functionality.

        Args:
            parent (QtGui.QDialog): parent dialog
        """
        super(OpenHipFile, self).__init__(parent)

        self._setup_ui()
        self.resize(1100, 500)

    def _setup_ui(self):
        # set up title including show and shot info
        self.setWindowTitle(
            QtGui.QApplication.translate(
                "Open Hip File",
                "Open or Import Hip File",
                None,
            )
        )
        # Create tree:
        self._tree = TreeView()
        self.model = TreeModel()
        self._tree.setModel(self.model)
        # Alternate color between lines
        self._tree.setAlternatingRowColors(1)

        self._layout = QtGui.QVBoxLayout()
        self._layout.addWidget(self._tree)

        # Add Load and Import button on the bottom of UI
        self.load_button = QtGui.QPushButton("Load")
        self.import_button = QtGui.QPushButton("Import")
        # Create layout for the buttons.
        button_layout = QtGui.QHBoxLayout()
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.import_button)
        # Add to main layout.
        self._layout.addItem(button_layout)
        self.setLayout(self._layout)
        # Set up connections.
        self._connect_widgets()

        # Double click option.
        self._tree.doubleClicked.connect(self.load_hip_file)

    def _connect_widgets(self):
        self.load_button.clicked.connect(self.load_hip_file)
        self.import_button.clicked.connect(self.import_hip_file)

    def load_hip_file(self):
        """Load file in scene."""
        if not HOUDINI:
            print "LOADING"
            return

        filepath = self.get_file_path()

        user_confirmation = QtGui.QMessageBox.question(
            self,
            "Loading hip file",
            "Are you sure you want to load {0}?".format(filepath),
            QtGui.QMessageBox.Yes | QtGui.QMessageBox.Cancel,
        )
        if user_confirmation == QtGui.QMessageBox.Yes and not filepath == "":
            if os.path.isfile(filepath):
                LOG.info("Selected file found... Loading -> %s", filepath)
                hou.hipFile.load(filepath)
                self.close()
            else:
                error_message = "Selected file not found -> {0}".format(filepath)
                LOG.error(error_message)
                hou.ui.displayMessage(error_message)

    def import_hip_file(self):
        """Import hip file in scene."""
        if not HOUDINI:
            print "IMPORTING"
            return
        filepath = self.get_file_path()
        LOG.info("Merging selected file %s", filepath)
        if not filepath == "":
            if os.path.isfile(filepath):
                LOG.warn("File found.. Merging -> %s", filepath)
                hou.hipFile.merge(filepath)
                self.close()
            else:
                error_message = "Selected file not found -> {0}".format(filepath)
                LOG.error(error_message)
                hou.ui.displayMessage(error_message)


def run_this_thing():
    print " --- RUNNING ---"
    app = QtGui.QApplication([])
    window = OpenHipFile()
    window.show()
    app.exec_()


tree = run_this_thing()
