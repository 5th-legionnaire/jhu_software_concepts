'''Base application for the a Flask-based personal website.'''

from flask import Flask

def create_app():
    '''Create and configure the Flask application using app factory approach.'''
    app = Flask(__name__)
    return app
