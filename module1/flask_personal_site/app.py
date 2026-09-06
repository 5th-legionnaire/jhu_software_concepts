'''Base application for the a Flask-based personal website.'''

from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello, Welcome to My Personal Website!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)