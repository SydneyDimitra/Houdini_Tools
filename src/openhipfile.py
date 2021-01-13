from PyQt4 import (QtCore, QtGui)

class TreeItem(object):
    def __init__(self, data=None, parent=None):
        self._data = data
        self._parent = parent

        self._children = []

    @property
    def children(self):
        return self._children

    def child(self, row):
        """Returns the child that corresponds to the specified row number
        in the item’s list of child items
        """
        if (row < 0 or row >= len(self._children)):
            return None
        return self._children[row]

    def childCount(self):
        """ """
        return len(self._children)

    def columnCount(self):
        return 1

    def data(self, column):
        if column == 0:
            return self._data["name"]
        else:
            return None

    def row(self):
        if self._parent:
            return self._parent.children.index(self)
        return -1

    def parentItem(self):
        return self._parent

    def appendChild(self, child):
        self._children.append(child)


class TreeModel(QtCore.QAbstractItemModel):
    def __init__(self):
        """ """
        super(TreeModel, self).__init__()
        self._rootItem = TreeItem(data={"name":"root"}, parent=None) 

    def data(self, index, role):
        """ """
        pass

    def flags(self, index):
        pass

    def headerData(self, section, orientation, role):
        pass

    def index(self, row, column, parent):
        pass

    def parent(self, index):
        pass

    def rowCount(self, parent):
        pass

    def columnCount(self, parent):
        pass


class TreeView(QtCore.QTreeView):
    def __init__(self):
        """ """
        super(TreeView, self).__init__()
