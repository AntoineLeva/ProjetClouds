import json
import os
import shutil
import subprocess
import threading

from flask import Flask, app, jsonify, request
from flask_cors import CORS
import paramiko

from ProjetCouldsV.ProjetClouds.appV6 import ssh_run_command

app = Flask(__name__)
CORS(app)

# Récupération des paramètres de la requête
# vm_ip = '192.168.66.192'  # IP de la VM
# user = 'imt'  # Utilisateur de la VM
# password = 'admin'  # Mot de passe de la VM
# repo_url = 'https://github.com/AntoineLeva/ProjetClouds.git'  # URL du dépôt
# temp_clone_dir = os.path.join(os.getcwd(), 'temp_repo')  # Dossier temporaire pour cloner le dépôt

def extract_repo_info(repo_url):
    """
    Extraire le nom de l'utilisateur et le nom du dépôt à partir de l'URL Git.
    Exemple : https://github.com/AntoineLeva/ProjetClouds.git -> ('AntoineLeva', 'ProjetClouds')
    """
    repo_parts = repo_url.strip('/').split('/')
    user = repo_parts[-2]  # L'utilisateur est l'avant-dernier élément
    repo_name = repo_parts[-1].replace('.git', '')  # Le nom du dépôt sans l'extension .git
    return user+"_"+repo_name+".json"

class PipelineData:
    def __init__(self, vm_ip, user, password, repo_url):
        self.vm_ip = vm_ip
        self.user = user
        self.password = password
        self.repo_url = repo_url
        self.temp_clone_dir = os.path.join(os.getcwd(), 'temp_repo')  # Dossier temporaire pour cloner le dépôt
        print(self.temp_clone_dir)

class Step:
    def __init__(self, name, function):
        self.name = name
        self.function = function
        self.status = "pending"  # pending, running, success, failed
    
    def run(self, data):
        try:
            self.status = "running"
            self.function(data)
            self.status = "success"
        except Exception as e:
            self.status = "failed"
            print(f"Step '{self.name}' failed: {e}")

def remove_readonly(func, path, _):
    """Change les permissions et supprime les fichiers en lecture seule."""
    os.chmod(path, 0o777)
    func(path)

def scp_directory(vm_ip, user, password, local_dir, remote_dir):
    """Copie un répertoire vers la VM via SCP avec tout son contenu récursivement."""
    try:
        transport = paramiko.Transport((vm_ip, 22))
        transport.connect(username=user, password=password)

        sftp = paramiko.SFTPClient.from_transport(transport)

        for root, dirs, files in os.walk(local_dir):
            # Calculer le chemin distant
            relative_path = os.path.relpath(root, local_dir)
            remote_path = os.path.join(remote_dir, relative_path).replace("\\", "/")  # Compatibilité Unix

            # Créer les répertoires distants de manière récursive
            try:
                sftp.stat(remote_path)  # Vérifie si le répertoire existe déjà
            except FileNotFoundError:
                parts = remote_path.split("/")
                for i in range(1, len(parts) + 1):
                    partial_path = "/".join(parts[:i])
                    try:
                        sftp.mkdir(partial_path)
                        print(f"Répertoire distant créé : {partial_path}")
                    except IOError:
                        pass  # Si le répertoire existe déjà, ignorer

            # Transférer les fichiers du répertoire courant
            for file in files:
                local_file_path = os.path.join(root, file)
                remote_file_path = os.path.join(remote_path, file).replace("\\", "/")
                print(f"Transfert fichier : {local_file_path} --> {remote_file_path}")
                sftp.put(local_file_path, remote_file_path)

        sftp.close()
        transport.close()
        print("Transfert complet du répertoire avec succès.")
        return True
    except Exception as e:
        print(f"Erreur lors du transfert du répertoire via SCP : {e}")
        raise e

# Étape 1 : Clonage du dépôt GitHub
def clone_repository(data):
    if os.path.exists(data.temp_clone_dir):
        print(f"Suppression du dossier temporaire : {data.temp_clone_dir}")
        shutil.rmtree(data.temp_clone_dir, onerror=remove_readonly)

    print(f"Clonage du dépôt {data.repo_url} dans {data.temp_clone_dir}...")
    os.system(f'git clone "{data.repo_url}" "{data.temp_clone_dir}"')
    if not os.path.isdir(data.temp_clone_dir):
        raise Exception("Clonage du dépôt échoué.")

# Étape 2 : Vérifier les TU
def verif_TU(data):
    print(f"Vérficiation des tests unitaires")
    maven_command = f'mvn test -f "{os.path.join(data.temp_clone_dir, "pom.xml")}"'
    
    try:
        exit_code = os.system(maven_command)

        if (exit_code == 0):
            print("Tests réussis !")
        else:
            raise Exception("Tests unitaire non passés.")
            
    except Exception as e:
        raise Exception("Tests unitaire non passés.")

# Étape 3 : Transfert vers la VM
def transfer_to_vm(data):
    print(f"Copie du dépôt cloné vers la VM {data.vm_ip}...")
    success = scp_directory(data.vm_ip, data.user, data.password, data.temp_clone_dir, f"/home/{data.user}/repo")
    if not success:
        raise Exception("Transfert vers la VM échoué.")

def stop_delete_docker_container(data):
     # Étape 4 : Arrêter et supprimer les conteneurs existants sur la VM
    print(f"Arrêt et suppression des conteneurs en cours sur la VM {data.vm_ip}...")
    stop_command = "docker ps -q | xargs -r docker stop"
    remove_command = "docker ps -a -q | xargs -r docker rm"
    ssh_run_command(data.vm_ip, data.user, data.password, stop_command)
    ssh_run_command(data.vm_ip, data.user, data.password, remove_command)

def create_backup(data):
     # Étape 5 : Créer un backup de l'image existante
    print(f"Création d'un backup de l'image 'repo_app' sur la VM {data.vm_ip}...")
    ssh_run_command(data.vm_ip, data.user, data.password, "mkdir -p /home/imt/backupup")  # Créer le dossier de backup

    # Vérifier si l'image existe avant de sauvegarder
    check_image_cmd = "docker images -q repo_app"
    image_id, _ = ssh_run_command(data.vm_ip, data.user, data.password, check_image_cmd)

    if image_id.strip():  # Si l'image existe
        backup_cmd = f"docker save {image_id.strip()} -o /home/imt/backupup/repo_app_backup.tar"
        backup_output, backup_error = ssh_run_command(data.vm_ip, data.user, data.password, backup_cmd)
        print("Backup output : ", backup_output)
        print("Backup error : ", backup_error)

        if backup_error:
            raise Exception("Erreur lors de la sauvegarde de l'image.")
    else:
        print("Aucune image 'repo_app' trouvée pour backup.")
        # raise Exception("Aucune image Docker trouvée pour backup.")

def delete_image_copy(data):
    # Vérifier si l'image existe avant de sauvegarder
    check_image_cmd = "docker images -q repo_app"
    image_id, _ = ssh_run_command(data.vm_ip, data.user, data.password, check_image_cmd)

    # Étape 6 : Supprimer l'image Docker existante
    if image_id.strip():  # supp si pb 
        print(f"Suppression de l'image Docker 'repo_app'...")
        remove_image_cmd = f"docker rmi -f {image_id.strip()}"
        remove_output, remove_error = ssh_run_command(data.vm_ip, data.user, data.password, remove_image_cmd)
        print("Remove output : ", remove_output)
        print("Remove error : ", remove_error)

def lauch_docker_compose(data):
    # Étape 7 : Lancer Docker Compose sur la VM
    print(f"Lancement de Docker Compose sur la VM {data.vm_ip}...")
    compose_cmd = f"cd /home/{data.user}/repo && docker-compose up -d --build"
    compose_output, compose_error = ssh_run_command(data.vm_ip, data.user, data.password, compose_cmd)
    print("Compose output : ", compose_output)
    print("Compose error : ", compose_error)

def sonar_qube(data):
    print(f"Vérficiation des tests sonarQube")
    maven_command = f'mvn sonar:sonar -Dsonar.host.url=http://localhost:9000/ -Dsonar.login=sqp_3cd56b2f5f80408d3f4925a724fb1e737c58f143 -X -f /home/imt/repo/pom.xml'
    # maven_command = f'mvn sonar:sonar -Dsonar.host.url=http://localhost:9000/ -Dsonar.login=sqp_3cd56b2f5f80408d3f4925a724fb1e737c58f143'
    try:
        # Création d'un client SSH
        ssh = paramiko.SSHClient()

        # Ajouter la clé de l'hôte si nécessaire
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connexion à la VM via SSH
        ssh.connect(data.vm_ip, username=data.user, password=data.password)

        # Exécution de la commande Maven sur la VM
        stdin, stdout, stderr = ssh.exec_command(maven_command)

        # Récupérer la sortie et l'erreur
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')

        if error:
            print("Erreur Maven :")
            print(error)
            raise error
        else:
            print(output)

        # Fermer la connexion SSH
        ssh.close()
            
    except Exception as e:
        raise e

# Définition des étapes
steps = [
    Step("Cloner le dépôt GitHub", clone_repository),
    Step("Vérifier les tests unitaires", verif_TU),
    Step("Transfert du code sur la VM", transfer_to_vm),
    Step("Arrêt et suppression des conteneurs en cours sur la VM", stop_delete_docker_container),
    Step("Créer un backup de l'image existante", create_backup),
    Step("Supprimer l'ancienne image", delete_image_copy),
    Step("Lancement de Docker Compose sur la VM", lauch_docker_compose),
    Step("Vérification de SonarQube", sonar_qube)
]

class Pipeline:
    def __init__(self, steps, state_file="pipeline_state.json"):
        self.steps = steps
        self.state_file = state_file
        
    def save_state(self):
        state = {step.name: step.status for step in self.steps}
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=4)

    def load_state(self):
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
            for step in self.steps:
                step.status = state.get(step.name, "pending")
        except FileNotFoundError:
            pass

    def run(self, data):
        for step in self.steps:
            if step.status in ["pending", "failed"]:
                try:
                    step.run(data)
                except:
                    return jsonify({"status": "error", "message": "erreur"}), 500 
                finally:
                    self.save_state()

@app.route('/create-pipeline', methods=['POST'])
def create_pipeline():
    
    # Récupérer les données de la requête
    data = request.json or {}
    vm_ip = data.get('vm_ip', '192.168.66.192')
    user = data.get('user', 'imt')
    password = data.get('password', 'admin')
    repo_url = data.get('repo_url', 'https://github.com/AntoineLeva/ProjetClouds.git')

    file_name = extract_repo_info(repo_url)
    pipeline = Pipeline(steps, file_name)
    pipeline.save_state()
    return

# Création de la pipeline
# pipeline = Pipeline(steps)

def run_process(repo_url, data):
    try:
        file_name = extract_repo_info(repo_url)
        pipeline = Pipeline(steps, file_name)
        pipeline.load_state()
        pipeline.run(data)
    except Exception as e:
        print(f"Erreur dans le processus de pipeline pour {repo_url}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/start-pipeline', methods=['POST'])
def start_pipeline():
    # Récupérer les données de la requête
    data = request.json or {}
    vm_ip = data.get('vm_ip', '192.168.66.192')
    user = data.get('user', 'imt')
    password = data.get('password', 'admin')
    repo_url = data.get('repo_url', 'https://github.com/AntoineLeva/ProjetClouds.git')

    # Créer un objet PipelineData avec les informations
    pipeline_data = PipelineData(vm_ip, user, password, repo_url)

    # Lancer le processus dans un thread séparé
    thread = threading.Thread(target=run_process, args=(repo_url, pipeline_data))
    thread.start()

    return jsonify({"message": "Processus démarré"})

# Fonction utilitaire pour lire l'état de la pipeline
def get_pipeline_state(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r") as f:
            return json.load(f)
    return {}  # Si le fichier n'existe pas, retourne un état vide

@app.route('/get-pipeline-status', methods=['POST'])
def get_pipeline_status():
    data = request.json or {}
    vm_ip = data.get('vm_ip', '192.168.66.192')
    user = data.get('user', 'imt')
    password = data.get('password', 'admin')
    repo_url = data.get('repo_url', 'https://github.com/AntoineLeva/ProjetClouds.git')

    file_name = extract_repo_info(repo_url)

    state = get_pipeline_state(file_name)
    return jsonify(state)

if __name__ == '__main__':
    app.run(debug=True, port=5001)