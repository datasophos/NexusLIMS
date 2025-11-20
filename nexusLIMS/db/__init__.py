"""
A module to handle communication with the NexusLIMS database.

Also performs basic database ORM tasks. The top-level module has a helper function to
make a database query (:py:meth:`make_db_query`), while the
:py:mod:`~nexusLIMS.db.session_handler` submodule is primarily concerned with mapping
session log information from the database into python objects for use in other parts of
the NexusLIMS backend.
"""

import contextlib
import os
import sqlite3


def make_db_query(query):
    """
    Execute a query on the NexusLIMS database and return the results as a list.

    Parameters
    ----------
    query : str
        The SQL query to execute

    Returns
    -------
    res_list : :obj:`list` of :obj:`tuple`
        The results of the SQL query
    """
    # use contextlib to auto-close the connection and database cursors
    with (
        contextlib.closing(
            sqlite3.connect(os.environ["NEXUSLIMS_DB_PATH"]),
        ) as connection,
        connection,
        contextlib.closing(connection.cursor()) as cursor,
    ):
        results = cursor.execute(query)
        return results.fetchall()
