import click

import flask.cli

import gocd_dashboard


@click.group(cls=flask.cli.FlaskGroup, create_app=gocd_dashboard.create_app)
def main():
    """Application management CLI."""
    pass

if __name__ == '__main__':
    main()
