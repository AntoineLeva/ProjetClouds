# Tuto-Web-service


Le ppt de tuto est a la racine du projet

Il n'y a pas les vidéos de test postman, ça arrivera prochainement

## Commande docker

docker build -t nom_image .
docker run -d --name nom_du_container -p 8080:8080 nom_image


docker-compose build -----> créer une image
docker-compose up -d -----> lancer les conteneur
docker-compose down  -----> arreter et supprimer les conteneurs existants
docker volume prune  -----> SUPPRIMER TOUS LES VOLUMES (ne pas faire merci)

## Information Sonarqube
Sonarqube : localhost:9000
user:admin
mdp :Sonar123456789@

mvn sonar:sonar -Dsonar.host.url=http://localhost:9000 -Dsonar.login=sqa_099f2e5294ccea95c11a14ad9dac9bd26b106b13

