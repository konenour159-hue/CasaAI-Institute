"""
Envoi d'emails transactionnels.

Aucun fournisseur d'envoi (SMTP, SendGrid, Postmark...) n'est configuré dans
ce projet — il n'y a jusqu'ici jamais eu besoin d'envoyer un email réel.
Le mot de passe oublié en a besoin, mais brancher un vrai fournisseur exige
des identifiants que seul le porteur du projet peut fournir.

En attendant : le lien est journalisé côté serveur plutôt qu'envoyé, ce qui
garde tout le reste du flux (génération du token, validation, changement de
mot de passe) fonctionnel et testable de bout en bout. Remplacer uniquement
le corps de `send_password_reset_email` par un vrai envoi (ex: via `smtplib`
avec les identifiants SMTP en variables d'environnement, ou l'API HTTP d'un
fournisseur) active l'envoi réel sans toucher au reste de l'application —
c'est le seul endroit qui doit changer.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("casa.email")


class EmailService:
    def send_password_reset_email(self, to_email: str, reset_url: str) -> None:
        logger.warning(
            "[EMAIL NON ENVOYÉ — aucun fournisseur configuré] "
            "Réinitialisation de mot de passe pour %s : %s",
            to_email, reset_url,
        )
