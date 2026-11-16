"""Stable QML rows: highlight changes must not reset the list or its scroll position."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class TranscriptModel(QAbstractListModel):
    RecordRole = int(Qt.UserRole) + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []

    def roleNames(self):
        return {self.RecordRole: b"record"}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and 0 <= index.row() < len(self._items) and role == self.RecordRole:
            return self._items[index.row()]
        return None

    def replace(self, rows, reset=False):
        before = self._items
        if reset or len(rows) < len(before):
            self.beginResetModel()
            self._items = rows
            self.endResetModel()
            return
        changed = [i for i in range(len(before)) if before[i] != rows[i]]
        if len(rows) > len(before):
            self.beginInsertRows(QModelIndex(), len(before), len(rows)-1)
            self._items = rows
            self.endInsertRows()
        else:
            self._items = rows
        if changed:
            self.dataChanged.emit(self.index(changed[0]), self.index(changed[-1]), [self.RecordRole])
