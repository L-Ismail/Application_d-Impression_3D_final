from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy  # Assurez-vous que ce module est bien installé

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

@app.route('/')
def home():
    return "Hello, Flask!"

if __name__ == '__main__':
    app.run(debug=True)
