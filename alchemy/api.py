import os

from github_bot_api.flask import create_flask_app

from alchemy.github import _webhook

if not os.environ["FLASK_ENV"]:
    os.environ["FLASK_ENV"] = "development"

flask_app = create_flask_app(__name__, _webhook)
flask_app.run()
