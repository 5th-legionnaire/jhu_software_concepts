'''Bluerprint for the board pages.'''

from flask import Blueprint

bp = Blueprint("pages", __name__)

@bp.route("/")
def home():
    '''This is the home page for the personal website.'''
    return "Hello, Welcome to My Personal Website!"

@bp.route("/contact_info")
def contact_info():
    '''This is the contact information page for the personal website.'''
    return "This is the contact information page for my personal website."

@bp.route("/projects_and_publications")
def projects_and_publications():
    '''This is the projects and publications page for the personal website.'''
    return "This is the projects and publications page for my personal website."