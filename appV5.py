from flask import Flask, request, jsonify
import os
import shutil
import paramiko

app = Flask(__name__)

def remove_readonly(func, path, _):
    """Change les permissions et supprime les fichiers en lecture seule."""
    os.chmod(path, 0o777)
    func(path)

def ssh_run_command(vm_ip, user, password, command):
    """Exécute une commande SSH sur la VM avec mot de passe."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(vm_ip, username=user, password=password)
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        ssh.close()
        return output, error
    except Exception as e:
        ssh.close()
        raise e

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
    except Exception as e:
        print(f"Erreur lors du transfert du répertoire via SCP : {e}")
        raise e

@app.route('/deploy', methods=['POST'])
def deploy():
    # Récupération des paramètres de la requête
    vm_ip = request.json.get('vm_ip', '192.168.66.192')  # IP de la VM
    user = request.json.get('user', 'imt')  # Utilisateur de la VM
    password = request.json.get('password', 'admin')  # Mot de passe de la VM
    repo_url = request.json.get('repo_url', 'https://github.com/AntoineLeva/ProjetClouds.git')  # URL du dépôt
    temp_clone_dir = os.path.join(os.getcwd(), 'temp_repo')  # Dossier temporaire pour cloner le dépôt

    try:
        # Étape 1 : Nettoyer le dossier temporaire local
        if os.path.exists(temp_clone_dir):
            print(f"Suppression du dossier temporaire : {temp_clone_dir}")
            shutil.rmtree(temp_clone_dir, onerror=remove_readonly)

        # Étape 2 : Cloner le dépôt GitHub
        print(f"Clonage du dépôt {repo_url} dans {temp_clone_dir}...")
        os.system(f"git clone {repo_url} {temp_clone_dir}")

        # Vérification que le clonage a réussi
        if not os.path.isdir(temp_clone_dir):
            return jsonify({"status": "error", "message": "Clonage du dépôt échoué."}), 404

        # Étape 3 : Transfert du dépôt cloné vers la VM
        print(f"Copie du dépôt cloné vers la VM {vm_ip}...")
        scp_directory(vm_ip, user, password, temp_clone_dir, f"/home/{user}/repo")

        # Étape 4 : Arrêter et supprimer les conteneurs existants sur la VM
        print(f"Arrêt et suppression des conteneurs en cours sur la VM {vm_ip}...")
        stop_command = "docker ps -q | xargs -r docker stop"
        remove_command = "docker ps -a -q | xargs -r docker rm"
        ssh_run_command(vm_ip, user, password, stop_command)
        ssh_run_command(vm_ip, user, password, remove_command)

        # Étape 5 : Créer un backup de l'image existante
        print(f"Création d'un backup de l'image 'repo_app' sur la VM {vm_ip}...")
        ssh_run_command(vm_ip, user, password, "mkdir -p /home/imt/backupup")  # Créer le dossier de backup

        # Vérifier si l'image existe avant de sauvegarder
        check_image_cmd = "docker images -q repo_app"
        image_id, _ = ssh_run_command(vm_ip, user, password, check_image_cmd)

        if image_id.strip():  # Si l'image existe
            backup_cmd = f"docker save {image_id.strip()} -o /home/imt/backupup/repo_app_backup.tar"
            backup_output, backup_error = ssh_run_command(vm_ip, user, password, backup_cmd)
            print("Backup output : ", backup_output)
            print("Backup error : ", backup_error)

            if backup_error:
                return jsonify({"status": "error", "message": "Erreur lors de la sauvegarde de l'image."}), 500
        else:
            print("Aucune image 'repo_app' trouvée pour backup.")
            return jsonify({"status": "error", "message": "Aucune image Docker trouvée pour backup."}), 404

        # Étape 6 : Supprimer l'image Docker existante
        if image_id.strip():  # Si l'image existe     //si pb enlever le if
            print(f"Suppression de l'image Docker 'repo_app'...")
            remove_image_cmd = f"docker rmi -f {image_id.strip()}"
            remove_output, remove_error = ssh_run_command(vm_ip, user, password, remove_image_cmd)
            print("Remove output : ", remove_output)
            print("Remove error : ", remove_error)

        # Étape 7 : Lancer Docker Compose sur la VM
        print(f"Lancement de Docker Compose sur la VM {vm_ip}...")
        compose_cmd = f"cd /home/{user}/repo && docker-compose up -d --build"
        compose_output, compose_error = ssh_run_command(vm_ip, user, password, compose_cmd)
        print("Compose output : ", compose_output)
        print("Compose error : ", compose_error)

        if compose_error:
            return jsonify({"status": "error", "message": compose_error}), 500

        return jsonify({"status": "success", "output": compose_output}), 200

    except Exception as e:
        print(f"Erreur générale : {e}")
        return jsonify({"status": "error", "message": str(e)}), 500





if __name__ == '__main__':
    app.run(debug=True)
