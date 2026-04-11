#!/usr/bin/env python3
"""
Script de configuration des identifiants de connexion.
Lancer une seule fois : python setup_auth.py
"""
import getpass
from auth import save_auth

print("\n╔══════════════════════════════════════════════╗")
print("║  Configuration des accès — Réservations VP   ║")
print("╚══════════════════════════════════════════════╝\n")

username = input("Identifiant (nom d'utilisateur) : ").strip()
if not username:
    print("❌ Identifiant vide. Abandon.")
    exit(1)

password = getpass.getpass("Mot de passe : ")
if len(password) < 6:
    print("❌ Le mot de passe doit faire au moins 6 caractères.")
    exit(1)

password2 = getpass.getpass("Confirmer le mot de passe : ")
if password != password2:
    print("❌ Les mots de passe ne correspondent pas.")
    exit(1)

pin = input("PIN (4 chiffres pour connexion rapide mobile) : ").strip()
if not pin.isdigit() or len(pin) != 4:
    print("❌ Le PIN doit être exactement 4 chiffres.")
    exit(1)

save_auth(username, password, pin)
print(f"\n✅ Identifiants enregistrés pour '{username}'.")
print("   Vous pouvez maintenant lancer l'application.\n")
