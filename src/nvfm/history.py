# -*- coding: future_fstrings -*-

class History:
    """Location history.

    The history object maintains a list of locations the user has previously
    navigated to. Navigating and adding to the history works the same as in a
    web browser.
    """
    def __init__(self):
        self._entries = []
        # Pointer to the currently viewed history entry
        self._pointer = -1

    def __repr__(self):
        s = ', '.join(('*' + str(x) if i == self._pointer else str(x))
                      for i, x in enumerate(self._entries))
        return f'History({s})'

    @property
    def all(self):
        """Return a copy of all history entries."""
        return self._entries[:]

    def add(self, item):
        """Add `item` to history.

        If the pointer doesn't point to the last history entry, the list will
        be truncated before appending `item`.
        """
        # Don't add same entry twice
        if self._entries and self._entries[self._pointer] == item:
            return
        # Truncate history, if we're not at the last entry
        if self._pointer < len(self._entries) - 1:
            self._entries = self._entries[:self._pointer + 1]
        self._entries.append(item)
        self._pointer = len(self._entries) - 1

    def go(self, step):
        """Move `step` in history and return the current item.

        If `step` is positive, move towards newer entries, otherwise older.
        Raises `IndexError` if new pointer is out of bounds.
        """
        new_p = self._pointer + step
        if not 0 <= new_p < len(self._entries):
            raise IndexError('History entry index out of range.')
        self._pointer = new_p
        return self._entries[new_p]
