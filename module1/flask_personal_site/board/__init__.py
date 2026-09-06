'''App initializer for the a Flask-based personal website.'''

from flask import Flask

from board import pages

def create_app():
    '''Create and configure the Flask application using app factory approach.'''
    app = Flask(__name__)
    app.register_blueprint(pages.bp)
    return app

