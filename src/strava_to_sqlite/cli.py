import threading
from queue import Queue

import click
import sqlite_utils

from .utils import (
    TempAuthCodeReqHandler,
    TempAuthCodeServer,
    User,
    ensure_tables,
    pick_port,
)


@click.group()
@click.version_option()
def cli():
    "Save data from Strava to a SQLite database"


@cli.command()
@click.argument(
    "db_path",
    type=click.Path(file_okay=True, dir_okay=False, allow_dash=False),
    required=True,
)
def auth(db_path):
    port = pick_port()
    click.echo(
        click.style("1. Visit ", fg="green")
        + click.style("https://www.strava.com/settings/api", fg="yellow")
        + click.style(" and create an application", fg="green")
    )
    click.secho(
        '2. In the "Authorization Callback Domain" field, put "localhost"', fg="green"
    )
    click.secho(
        '3. You\'ll have access to "ClientID" and "Client Secret" once created. Paste them below:',
        fg="green",
    )
    client_id = click.prompt("Enter ClientID")
    client_secret = click.prompt("Enter Client Secret")

    click.echo(
        click.style("4. Open link and authorize: ", fg="green")
        + click.style(
            f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri=http://localhost:{port}/exchange_token&approval_prompt=force&scope=read_all,profile:read_all,activity:read_all",
            fg="yellow",
        )
    )

    # NOTE: Instead of using event, we could also call another thread and call shutdown from it.
    # https://stackoverflow.com/questions/19040055/how-do-i-shutdown-an-httpserver-from-inside-a-request-handler-in-python
    exitServer = threading.Event()
    q = Queue()
    with TempAuthCodeServer(
        ("localhost", port), TempAuthCodeReqHandler, exitServer, q
    ) as server:
        t = threading.Thread(target=server.serve_forever)
        t.daemon = True
        t.start()
        exitServer.wait()
        server.shutdown()
    if not q.empty():
        auth_code = q.get()
        db = sqlite_utils.Database(db_path)
        ensure_tables(db)
        user = User(client_id=client_id, client_secret=client_secret)
        user.initial_access_token(db, auth_code)


@cli.command()
@click.argument(
    "db_path",
    type=click.Path(file_okay=True, dir_okay=False, allow_dash=False),
    required=True,
)
def sync(db_path, username):
    db = sqlite_utils.Database(db_path)
    # NOTE: Since all users at the moment are using their own API keys, this
    # can be run in parallel later.
    all_users = [User(**u) for u in db.query("SELECT * FROM users")]
    for user in all_users:
        if user.access_expired():
            user.refreshed_access_token(db)
        user.fetch_activities(db)
