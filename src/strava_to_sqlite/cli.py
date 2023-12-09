from sqlite_utils import Database
import click

@click.group()
@click.version_option()
def cli():
    "Save data from Strava to a SQLite database"
