"""Shared plumbing for offline jobs: database session, logging and HTTPS settings."""

import contextlib
import io
import logging
import ssl
import sys
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from infrastructure.db.engine import create_db_engine
from infrastructure.db.session import create_session_factory
from infrastructure.settings import Settings


@contextmanager
def job_session() -> Iterator[Session]:
    """One transaction for the whole job: committed at the end, rolled back on any error.

    A job that fails half-way therefore leaves the database as it found it.
    """
    engine = create_db_engine(Settings().database_url)
    try:
        with create_session_factory(engine).begin() as session:
            yield session
    finally:
        engine.dispose()


@contextmanager
def job_sessions() -> Iterator[sessionmaker[Session]]:
    """A session factory for jobs that need short transactions of their own,
    such as counting model requests against the daily allowance."""
    engine = create_db_engine(Settings().database_url)
    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def configure_logging() -> None:
    """Set up console output for a job run from the command line."""
    # Area names contain umlauts; the Windows console's default encoding garbles them.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # The HTTP library logs every request it makes; a job's own lines are enough.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def https_context() -> ssl.SSLContext:
    """TLS settings for job downloads. Certificates and host names are always verified.

    On Windows, Python's default context trusts the machine's store of
    intermediate certificates as well as its root store. An expired intermediate
    in that store then makes sites with a perfectly valid certificate fail with
    "certificate has expired". Trusting only the root store, as browsers do,
    avoids this; the server sends the intermediates itself.
    """
    if sys.platform != "win32":
        return ssl.create_default_context()

    # PROTOCOL_TLS_CLIENT turns on certificate and host-name verification.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    server_auth = ssl.Purpose.SERVER_AUTH.oid
    for certificate, encoding, trust in ssl.enum_certificates("ROOT"):
        trusted_for_servers = trust is True or (trust is not False and server_auth in trust)
        if encoding == "x509_asn" and trusted_for_servers:
            # A root the TLS library cannot parse is skipped, as Python itself does.
            with contextlib.suppress(ssl.SSLError):
                context.load_verify_locations(cadata=certificate)
    return context
