Personal Website - Flask App (Module 1)
=========================================

This is a small Flask application for a personal website (home page,
projects & publications, and contact info), built with the Flask
application factory pattern (see board/__init__.py) and organized as
a Flask blueprint (see board/pages.py).

Requirements
------------
- Python 3.10 or higher (developed/tested on Python 3.14)

Setup
-----
1. From this directory (module1/flask_personal_site/), create a virtual
   environment:

     python3 -m venv venv

2. Activate it:

     source venv/bin/activate        (macOS/Linux)
     venv\Scripts\activate           (Windows)

3. Install dependencies:

     pip install -r requirements.txt

Running the app
----------------
With the virtual environment activated, from this directory run:

     python run.py

The site will start on http://0.0.0.0:8080 (open it in your browser at
http://localhost:8080).

Deactivating
------------
When you're done, exit the virtual environment with:

     deactivate

Project layout
--------------
run.py                   - Entry point; run with `python run.py`
requirements.txt          - Python dependencies needed to reconstruct the environment
board/
  __init__.py             - Flask app factory (create_app)
  pages.py                - Blueprint with route definitions (home, contact_info,
                             projects_and_publications)
  static/                 - CSS and images (styles.css, bio_photo.jpeg)
  templates/              - Jinja2 templates
    base.html             - Shared page layout (top nav bar, title)
    _navigation.html      - Navigation bar, included on every page
    pages/                - One template per route (home.html, contact_info.html,
                             projects_and_publications.html)

Grading Rubric (Module 1)
--------------------------
For reference, the assignment is graded against the following rubric:

GitHub Repository Setup and Submission (15 pts)
  - Private GitHub repository named jhu_software_concepts is created and
    shared with instructor/grader: 4 pts
  - Repository contains a clearly organized module_1 folder: 3 pts
  - Student uses Git throughout development with meaningful commits rather
    than one final upload: 4 pts
  - SSH URL is submitted correctly: 2 pts
  - Final Canvas submission includes zipped files and matches the GitHub
    version: 2 pts

Flask Application Functionality (15 pts)
  - Application uses Flask as the web framework: 4 pts
  - Website starts successfully using python run.py: 4 pts
  - Application runs on port 8080 using localhost or 0.0.0.0: 3 pts
  - Site loads without runtime errors or missing route errors: 3 pts
  - Uses Python 3.10 or higher: 1 pt

Required Website Pages and Content (25 pts)
  - Homepage includes student name, position/title, biography, and
    picture: 6 pts
  - Homepage layout places bio text on the left and image on the right:
    3 pts
  - Contact page includes email address: 3 pts
  - Contact page includes LinkedIn information or link: 3 pts
  - Projects/publications page includes Module 1 project title: 3 pts
  - Projects/publications page includes meaningful details about the
    Module 1 project: 4 pts
  - Projects/publications page includes link to Module 1 GitHub project:
    3 pts

Navigation Bar Requirements (15 pts)
  - Site includes a navigation bar: 3 pts
  - Each page can be accessed from the navigation bar: 4 pts
  - Navigation bar appears consistently in the top-right corner of each
    page: 3 pts
  - Current tab/page is highlighted: 3 pts
  - Highlighted tab is colorized differently from the rest of the page:
    2 pts

Project Structure and Reproducibility (15 pts)
  - Includes requirements.txt sufficient to reconstruct the environment:
    4 pts
  - Includes README.txt inside module_1 with clear instructions for
    running the site: 4 pts
  - Includes screenshots of each running site tab saved as a PDF in
    module_1: 4 pts
  - Uses appropriate templates folder structure: 2 pts
  - Uses appropriate static folder structure: 1 pt

Design, CSS, and User Experience (8 pts)
  - Uses CSS to control formatting, colors, spacing, and visual layout:
    3 pts
  - Website is readable, visually organized, and professional: 3 pts
  - Pages are creative/personalized while remaining functional: 2 pts

Code Quality and Maintainability (7 pts)
  - Code is clear, organized, and easy to follow: 2 pts
  - Variable, file, route, and function names are appropriate: 2 pts
  - Code is well commented where helpful: 1 pt
  - Uses Flask blueprints: 2 pts
