from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
import subprocess
import shutil

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'

db = SQLAlchemy(app)

# Modèles
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    client_nom = db.Column(db.String(100), nullable=False)  # Add client name
    adresse = db.Column(db.String(200), nullable=False)  # Add address

class objet3d(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    libelle = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    chemin_fichier = db.Column(db.String(200), nullable=False)

class Parametre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    objet_id = db.Column(db.Integer, db.ForeignKey('objet3d.id'), nullable=False)
    code_variable = db.Column(db.String(50), nullable=False)
    libelle = db.Column(db.String(100), nullable=False)
    valeur_defaut = db.Column(db.Float, nullable=False)
    min_valeur = db.Column(db.Float, nullable=True)
    max_valeur = db.Column(db.Float, nullable=True)

class Commande(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_nom = db.Column(db.String(100), nullable=False)
    adresse = db.Column(db.String(200), nullable=False)
    date_commande = db.Column(db.DateTime, default=db.func.current_timestamp())
    date_livraison = db.Column(db.DateTime, nullable=True)
    objet_id = db.Column(db.Integer, db.ForeignKey('objet3d.id'), nullable=False)
    parametres = db.Column(db.Text, nullable=False)

class FichierModifie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    fichier_nom = db.Column(db.String(200), nullable=False)
    date_modification = db.Column(db.DateTime, default=db.func.current_timestamp())
    parametres = db.Column(db.Text, nullable=False)
    date_commande = db.Column(db.DateTime, default=db.func.current_timestamp())
    date_livraison = db.Column(db.DateTime, nullable=True)

# Ajouter des paramètres spécifiques des fichiers .scad à la base de données
def add_scad_files_to_db():
    scad_directory = os.path.join(os.getcwd(), 'fichiers_3D')
    param_pattern = re.compile(r'(\w+)\s*=\s*([\d.]+);')
    specific_params = {
        'Nut_Job.scad': ['head_diameter'],
        'sliding_top_box.scad': ['wallThick']
    }
    for filename in os.listdir(scad_directory):
        if filename.endswith('.scad'):
            chemin_fichier = os.path.join('fichiers_3D', filename)
            libelle = filename.replace('.scad', '').replace('_', ' ').title()
            description = f"Fichier 3D pour {libelle}"
            if not objet3d.query.filter_by(chemin_fichier=chemin_fichier).first():
                new_product = objet3d(libelle=libelle, description=description, chemin_fichier=chemin_fichier)
                db.session.add(new_product)
                db.session.commit()
                with open(chemin_fichier, 'r') as file:
                    for line in file:
                        match = param_pattern.match(line.strip())
                        if match:
                            code_variable, valeur_defaut = match.groups()
                            if filename in specific_params and code_variable in specific_params[filename]:
                                param = Parametre(
                                    objet_id=new_product.id,
                                    code_variable=code_variable,
                                    libelle=code_variable.replace('_', ' ').title(),
                                    valeur_defaut=float(valeur_defaut)
                                )
                                db.session.add(param)
                db.session.commit()

# Routes
@app.route('/')
def index():
    objets = objet3d.query.all()
    return render_template('index.html', objets=objets)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        client_nom = request.form['client_nom']  # Get client name
        adresse = request.form['adresse']  # Get address
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password, client_nom=client_nom, adresse=adresse)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Login failed. Check your username and/or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'user_id' not in session:
        flash('Please log in to access your account.', 'danger')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.client_nom = request.form['client_nom']  # Update client name
        user.adresse = request.form['adresse']  # Update address
        db.session.commit()
        flash('Account updated successfully!', 'success')
    fichiers_modifies = FichierModifie.query.filter_by(user_id=user.id).all()
    return render_template('account.html', user=user, fichiers_modifies=fichiers_modifies)

@app.route('/panier')
def panier():
    if 'user_id' not in session:
        flash('Please log in to access your cart.', 'danger')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    fichiers_modifies = FichierModifie.query.filter_by(user_id=user.id).all()
    return render_template('panier.html', fichiers_modifies=fichiers_modifies)

@app.route('/product/<int:objet_id>')
def product(objet_id):
    product = objet3d.query.get_or_404(objet_id)
    params = Parametre.query.filter_by(objet_id=objet_id).all()
    product_data = {
        "id": product.id,
        "name": product.libelle,
        "image": "lunettes.png",  # Remplace par product.chemin_fichier si c'est le vrai chemin
        "description": product.description,
        "params": params
    }
    return render_template('product.html', product=product_data)

@app.route('/modify_and_download/<int:objet_id>', methods=['POST'])
def modify_and_download(objet_id):
    product = objet3d.query.get_or_404(objet_id)
    params = Parametre.query.filter_by(objet_id=objet_id).all()
    scad_file_path = os.path.join(os.getcwd(), product.chemin_fichier)
    
    if not os.path.exists(scad_file_path):
        return f"File {scad_file_path} not found", 404

    modified_scad_content = []

    # Modifier le libellé du produit
    new_libelle = request.form.get('libelle')
    if new_libelle:
        product.libelle = new_libelle
        db.session.commit()

    parametres_modifies = {}
    with open(scad_file_path, 'r') as file:
        for line in file:
            if line.strip().startswith('head_diameter'):
                new_value = request.form.get('head_diameter')
                if new_value:
                    line = f"head_diameter = {new_value};\n"
                    parametres_modifies['head_diameter'] = new_value
            elif line.strip().startswith('wallThick'):
                new_value = request.form.get('wallThick')
                if new_value:
                    line = f"wallThick = {new_value};\n"
                    parametres_modifies['wallThick'] = new_value
            modified_scad_content.append(line)

    modified_scad_path = os.path.join(os.getcwd(), 'modified_' + os.path.basename(scad_file_path))
    with open(modified_scad_path, 'w') as file:
        file.writelines(modified_scad_content)

    # Vérifier si OpenSCAD est installé et accessible
    openscad_path = 'OpenSCAD/openscad.exe'  # Remplacez par le chemin réel vers OpenSCAD
    if not shutil.which(openscad_path):
        return f"OpenSCAD executable not found: {openscad_path}", 500

    # Lancer OpenSCAD pour générer le fichier STL
    stl_file_path = os.path.join(os.getcwd(), 'output_' + os.path.basename(scad_file_path).replace('.scad', '.stl'))
    try:
        result = subprocess.run([openscad_path, '-o', stl_file_path, modified_scad_path], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        return f"OpenSCAD failed: {e.stderr}", 500

    # Télécharger le fichier SCAD modifié avec le nouveau nom
    new_scad_file_path = os.path.join(os.getcwd(), (new_libelle or 'modified') + '.scad')
    os.rename(modified_scad_path, new_scad_file_path)

    date_commande = db.func.current_timestamp()
    date_livraison = db.func.date(db.func.current_timestamp(), '+2 days')

    # Enregistrer les informations du fichier modifié
    if 'user_id' in session:
        fichier_modifie = FichierModifie(
            user_id=session['user_id'],
            fichier_nom=new_scad_file_path,
            parametres=str(parametres_modifies),
            date_commande=date_commande,
            date_livraison=date_livraison
        )
        db.session.add(fichier_modifie)
        db.session.commit()

    return send_file(new_scad_file_path, as_attachment=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure tables are created first
        add_scad_files_to_db()
    app.run(debug=True)
