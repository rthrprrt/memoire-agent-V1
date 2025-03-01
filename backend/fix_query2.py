# Ouvrez le fichier main.py en mode lecture
with open("main.py", "r") as file:
    content = file.read()

# Remplacez toutes les occurrences de j.contenu par j.content
corrected_content = content.replace("j.contenu", "j.content")

# Écrivez le contenu corrigé dans le fichier
with open("main.py", "w") as file:
    file.write(corrected_content)

print("Correction appliquée avec succès!")