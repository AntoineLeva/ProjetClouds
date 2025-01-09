# Étape 1 : Utiliser une image de base avec Java installé
FROM openjdk:17-jdk-slim

# Étape 2 : Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Étape 3 : Copier le fichier JAR dans le conteneur
COPY target/tuto-0.0.1-SNAPSHOT.jar app.jar

# Étape 4 : Exposer un port (par exemple, 8080)
EXPOSE 8080

# Étape 5 : Spécifier la commande pour exécuter l'application
CMD ["java", "-jar", "app.jar"]
