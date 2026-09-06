'''Bluerprint for the board pages.'''

from flask import Blueprint

bp = Blueprint("pages", __name__)

@bp.route("/")
def home():
    '''This is the home page for the personal website.'''
    return render_template("pages/home.html")

@bp.route("/contact_info")
def contact_info():
    '''This is the contact information page for the personal website.'''
    return render_template("pages/contact_info.html")

@bp.route("/projects_and_publications")
def projects_and_publications():
    '''This is the projects and publications page for the personal website.'''
    return render_template("pages/projects_and_publications.html")