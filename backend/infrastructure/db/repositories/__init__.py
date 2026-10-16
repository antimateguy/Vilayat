"""PostgreSQL implementations of the ports.

Each repository receives a SQLAlchemy session and returns domain objects, so no
caller ever sees a table row or writes SQL.
"""
