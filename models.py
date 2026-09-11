from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


db = SQLAlchemy()


class Utilisateur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)
    nom = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telephone = db.Column(db.String(30))
    ville = db.Column(db.String(80))
    mot_de_passe_hash = db.Column(db.String(255), nullable=False)
    avatar_url = db.Column(db.String(255))
    bio = db.Column(db.String(255))
    profil_public = db.Column(db.Boolean, default=True)
    qui_peut_contacter = db.Column(db.String(30), default="tous")
    commentaires_autorises = db.Column(db.Boolean, default=True)
    tags_autorises = db.Column(db.Boolean, default=True)
    notif_messages = db.Column(db.Boolean, default=True)
    notif_demandes = db.Column(db.Boolean, default=True)
    notif_reservations = db.Column(db.Boolean, default=True)
    notif_collaborations = db.Column(db.Boolean, default=True)
    notif_interactions = db.Column(db.Boolean, default=True)
    notif_abonnes = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    profil_photographe = db.relationship("ProfilPhotographe", backref="utilisateur", uselist=False)
    publications = db.relationship("Publication", foreign_keys="Publication.utilisateur_id", backref="auteur", cascade="all, delete-orphan")

    def set_mot_de_passe(self, mot_de_passe):
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def verifier_mot_de_passe(self, mot_de_passe):
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)

    def nb_abonnes(self):
        return Abonnement.query.filter_by(suivi_id=self.id).count()

    def nb_abonnements(self):
        return Abonnement.query.filter_by(abonne_id=self.id).count()

    def est_suivi_par(self, utilisateur_id):
        if not utilisateur_id:
            return False
        return Abonnement.query.filter_by(abonne_id=utilisateur_id, suivi_id=self.id).first() is not None


class Publication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    legende = db.Column(db.String(255))
    photographe_credite_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"))
    album_id = db.Column(db.Integer, db.ForeignKey("album.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    photographe_credite = db.relationship("Utilisateur", foreign_keys=[photographe_credite_id])
    album = db.relationship("Album", foreign_keys=[album_id], back_populates="publication")
    likes = db.relationship("PublicationLike", backref="publication", cascade="all, delete-orphan")
    commentaires = db.relationship("Commentaire", backref="publication", cascade="all, delete-orphan")
    enregistrements = db.relationship("Enregistrement", backref="publication", cascade="all, delete-orphan")
    reposts = db.relationship("Repost", backref="publication", cascade="all, delete-orphan")

    def nb_likes(self):
        return PublicationLike.query.filter_by(publication_id=self.id).count()
    def nb_commentaires(self):
        return Commentaire.query.filter_by(publication_id=self.id).count()
    def nb_reposts(self):
        return Repost.query.filter_by(publication_id=self.id).count()
    def est_aimee_par(self, user_id):
        return bool(user_id and PublicationLike.query.filter_by(publication_id=self.id, utilisateur_id=user_id).first())
    def est_enregistree_par(self, user_id):
        return bool(user_id and Enregistrement.query.filter_by(publication_id=self.id, utilisateur_id=user_id).first())


class PublicationLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    publication_id = db.Column(db.Integer, db.ForeignKey("publication.id"), nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("publication_id", "utilisateur_id", name="uq_like"),)


class Commentaire(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    publication_id = db.Column(db.Integer, db.ForeignKey("publication.id"), nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    utilisateur = db.relationship("Utilisateur")


class Enregistrement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    publication_id = db.Column(db.Integer, db.ForeignKey("publication.id"), nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("publication_id", "utilisateur_id", name="uq_save"),)


class Repost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    publication_id = db.Column(db.Integer, db.ForeignKey("publication.id"), nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("publication_id", "utilisateur_id", name="uq_repost"),)


class Abonnement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    abonne_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    suivi_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("abonne_id", "suivi_id", name="uq_follow"),)


class Album(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    photographe_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservation.id"), nullable=True)
    titre = db.Column(db.String(120), nullable=False)
    categorie = db.Column(db.String(80))
    politique_telechargement = db.Column(db.String(20), default="client")  # client, tous, personne
    collaboration_acceptee = db.Column(db.Boolean, default=False)
    publication_visible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    photographe = db.relationship("Utilisateur", foreign_keys=[photographe_id], backref="albums")
    client = db.relationship("Utilisateur", foreign_keys=[client_id], backref="albums_collaboratifs")
    reservation = db.relationship("Reservation", foreign_keys=[reservation_id], backref="album", uselist=False)
    photos = db.relationship("PortfolioPhoto", backref="album", cascade="all, delete-orphan")
    publication = db.relationship("Publication", foreign_keys="Publication.album_id", back_populates="album", uselist=False)

    def photo_couverture(self):
        return self.photos[0] if self.photos else None


class PortfolioPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey("album.id"), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProfilPhotographe(db.Model):
    id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), primary_key=True)
    presentation = db.Column(db.Text)
    specialites = db.Column(db.String(255))
    annees_experience = db.Column(db.Integer, default=0)
    tarif_min = db.Column(db.Integer, default=0)
    note_moyenne = db.Column(db.Float, default=0.0)
    certifie = db.Column(db.Boolean, default=False)
    reseaux_sociaux = db.Column(db.String(255))
    disponibilite = db.Column(db.String(255), default="Disponible sur demande")
    visibilite_pro = db.Column(db.Boolean, default=True)

    def liste_specialites(self):
        if not self.specialites:
            return []
        return [s.strip() for s in self.specialites.split(",") if s.strip()]


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    photographe_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    type_prestation = db.Column(db.String(80))
    date_prestation = db.Column(db.String(40))
    budget = db.Column(db.Integer)
    message = db.Column(db.Text, nullable=False)
    statut = db.Column(db.String(20), default="en_attente")
    devis = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client = db.relationship("Utilisateur", foreign_keys=[client_id])
    photographe = db.relationship("Utilisateur", foreign_keys=[photographe_id])


class Avis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    photographe_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    note = db.Column(db.Integer, nullable=False)
    commentaire = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client = db.relationship("Utilisateur", foreign_keys=[client_id])
    photographe = db.relationship("Utilisateur", foreign_keys=[photographe_id])


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expediteur_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    destinataire_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    lu = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expediteur = db.relationship("Utilisateur", foreign_keys=[expediteur_id])
    destinataire = db.relationship("Utilisateur", foreign_keys=[destinataire_id])


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    destinataire_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    type = db.Column(db.String(40), nullable=False)
    titre = db.Column(db.String(180), nullable=False)
    contenu = db.Column(db.String(500))
    lien = db.Column(db.String(255))
    lu = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    destinataire = db.relationship("Utilisateur", foreign_keys=[destinataire_id], backref="notifications")
