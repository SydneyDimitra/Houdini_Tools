import logging
import os
import re

import humanize
import pendulum

from PyQt4 import (QtCore, QtGui)
# import hou

# Initialise the LOG object
LOG = logging.getLogger("simple example")
#LOG = logging.getLogger("dnhou.{0}".format(__name__))
LOG.setLevel(logging.INFO)


class PathTreeItem(object):
    def __init__(self, file_path, file_name=None, parent=None):
        """Construct a PathTreeItem object.

        Args:
            file_path (str): The full path of the file.
            file_name (str): The name of the file.
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
        self._is_loaded = loaded

    def get_contents(self):
        self._contents = get_contents(self.file_path)

    def data(self, column, role=QtCore.Qt.DisplayRole):
        if column == 0:
            if role == QtCore.Qt.DisplayRole:
                return self._file_name

            elif role == QtCore.Qt.UserRole:
                return self.file_path
        return super(PathTreeItem, self).data(column, role)

    def child(self, row):
        """Returns the child that corresponds to the specified row number
        in the items list of child items
        """
        if (row < 0 or row >= len(self._children)):
            return None
        return self._children[row]

    def childCount(self):
        """Return the number of child items held."""
        return len(self._children)

    def columnCount(self):
        return 1

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
        # Colouring the extra folders under the user folder for better
        # visibility (these include automated saved scene files that might
        # be handy)
        if role == QtCore.Qt.ForegroundRole and column == 0:
            if self.name.lower() in ["backup", "render"]:
                return QtGui.QColor(255, 255, 102)
        return super(FolderItem, self).data(column, role)


class FileGroupItem(PathTreeItem):
    """This class represents a file group tree item."""

    def __init__(self, file_path, parent=None):
        """Construct FileGroupItem object.

        Args:
            file_path (str): Full path of file.
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
        self.latest = self._get_latest()
        data = None

        if self.latest and role == QtCore.Qt.DisplayRole:
            column_data = [
                None,
                self.latest.name,
                self.latest.time,
                self.latest.size
            ]
            try:
                data = column_data[column]
            except IndexError:
                pass
        if data is None:
            data = super(FileGroupItem, self).data(column, role)
        return data


class FileItem(PathTreeItem):
    """This class represents a file tree item."""

    def __init__(self, file_path, parent=None):
        """Construct FileItem object.

        Args:
            file_path (str): Full path of file.
        """
        super(FileItem, self).__init__(file_path, parent=parent)
        self.date = None
        self.time = None
        self.size = self._get_file_size()
        self._evaluate_creation_date()

    def data(self, column, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            if column == 2:
                return self.time
            if column == 3:
                return self.size
        elif role == QtCore.Qt.ForegroundRole and column == 0:
            return QtGui.QColor(46, 187, 209)
        return super(FileItem, self).data(column, role)

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
    def __init__(self):
        """ """
        super(TreeModel, self).__init__()
        self._rootItem = PathTreeItem("root", parent=None)
        self._items = {}

    def data(self, index, role):
        """ """
        if not index.isValid():
            return QtCore.QVariant()

        if role != QtCore.Qt.DisplayRole:
            return QtCore.QVariant()

        item = index.internalPointer()

        return item.data(index.column())

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        """Return the data that we stored on the root item"""
        if (orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole):
            return self._rootItem.data(section)
        return QtCore.QVariant()

    def index(self, row, column, parent):
        """ """
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
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parentItem()

        if parentItem == self._rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        """Return the number of child items for the TreeItem that corresponds
        to a given model index, or the number of top-level items if an invalid
        index is specified:"""
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
