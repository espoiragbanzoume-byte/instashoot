import os
import threading
import uuid
import secrets
import hashlib
import re
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import date, datetime, timedelta
from models import db, Utilisateur, ProfilPhotographe, Album, PortfolioPhoto, Reservation, Avis, Publication, Abonnement, Message, PublicationLike, Commentaire, Enregistrement, Repost, Notification, DemandeReinitialisationMotDePasse

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///photoconnect.db")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cle-de-developpement-a-changer-plus-tard")
app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024  # 40 Mo par requête (plusieurs photos à la fois)

# Configuration Gmail pour la récupération du mot de passe.
# Les valeurs doivent être fournies par variables d'environnement, jamais dans GitHub.
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com").strip()
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "465"))
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "support.instashoot@gmail.com").strip()
# Google affiche parfois le mot de passe d'application avec des espaces.
# Ils sont retirés automatiquement pour éviter une erreur SMTP.
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "").replace(" ", "").strip()
app.config["RESET_CODE_EXPIRATION_MINUTES"] = 10
app.config["RESET_MAX_ATTEMPTS"] = 5
app.config["RESET_RESEND_DELAY_SECONDS"] = 60


os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

PRESTATIONS = ["Mariage", "Portrait", "Événementiel", "Mode", "Grossesse", "Produits", "Corporate", "Sport", "Lifestyle", "Photo scolaire"]

@app.context_processor
def donnees_formulaires():
    # Les villes déjà présentes dans la plateforme sont proposées directement.
    villes = [v for (v,) in db.session.query(Utilisateur.ville).filter(
        Utilisateur.ville.isnot(None), Utilisateur.ville != ""
    ).distinct().order_by(Utilisateur.ville.asc()).all()]
    # Quelques villes béninoises utiles restent disponibles même avant qu'elles
    # aient été enregistrées par un utilisateur.
    for ville in ["Cotonou", "Abomey-Calavi", "Porto-Novo", "Ouidah", "Parakou", "Bohicon", "Natitingou"]:
        if ville not in villes:
            villes.append(ville)
    villes.sort(key=lambda x: x.lower())
    return {"villes_disponibles": villes, "prestations_disponibles": PRESTATIONS}

EXTENSIONS_AUTORISEES = {"png", "jpg", "jpeg", "webp"}


def extension_autorisee(nom_fichier):
    return "." in nom_fichier and nom_fichier.rsplit(".", 1)[1].lower() in EXTENSIONS_AUTORISEES


def enregistrer_image(fichier):
    """Sauvegarde un fichier uploadé avec un nom unique, retourne son URL publique (ou None)."""
    if not fichier or fichier.filename == "":
        return None
    if not extension_autorisee(fichier.filename):
        return None

    extension = fichier.filename.rsplit(".", 1)[1].lower()
    nom_unique = f"{uuid.uuid4().hex}.{extension}"
    chemin = os.path.join(app.config["UPLOAD_FOLDER"], nom_unique)
    fichier.save(chemin)
    return url_for("static", filename=f"uploads/{nom_unique}")


db.init_app(app)


@app.errorhandler(413)
def fichier_trop_volumineux(e):
    return (
        "Les photos envoyées sont trop lourdes au total (40 Mo max par publication). "
        "Essaie avec moins de photos à la fois, ou des photos compressées. "
        "<a href=\"javascript:history.back()\">Retour</a>",
        413,
    )


def seeder_donnees_demo():
    """Ajoute quelques photographes de démo si la base est vide (une seule fois)."""
    if Utilisateur.query.filter_by(role="photographe").count() > 0:
        return

    demo = [
        {
            "nom": "Aristide K.", "email": "aristide@example.com", "ville": "Cotonou",
            "presentation": "Photographe passionné basé à Cotonou, spécialisé dans les mariages et l'événementiel depuis 5 ans.",
            "specialites": "Mariage, Portrait, Événementiel", "annees_experience": 5, "tarif_min": 50000,
        },
        {
            "nom": "Nadège S.", "email": "nadege@example.com", "ville": "Cotonou",
            "presentation": "Spécialisée en photographie de mode et portraits créatifs.",
            "specialites": "Mode, Portrait", "annees_experience": 3, "tarif_min": 35000,
        },
        {
            "nom": "Ferdinand A.", "email": "ferdinand@example.com", "ville": "Porto-Novo",
            "presentation": "7 ans d'expérience en photographie événementielle à Porto-Novo.",
            "specialites": "Mariage, Grossesse, Produits", "annees_experience": 7, "tarif_min": 60000,
        },
    ]

    for d in demo:
        u = Utilisateur(role="photographe", nom=d["nom"], email=d["email"], ville=d["ville"])
        u.set_mot_de_passe("motdepasse123")
        db.session.add(u)
        db.session.flush()  # pour obtenir u.id avant de créer le profil lié
        profil = ProfilPhotographe(
            id=u.id,
            presentation=d["presentation"],
            specialites=d["specialites"],
            annees_experience=d["annees_experience"],
            tarif_min=d["tarif_min"],
            note_moyenne=4.7,
        )
        db.session.add(profil)

    db.session.commit()


def creer_notification(destinataire_id, type_, titre, contenu="", lien=None):
    """Crée une notification interne, en respectant les préférences du compte."""
    u = Utilisateur.query.get(destinataire_id)
    if not u:
        return
    preference = {
        "message": "notif_messages", "demande": "notif_demandes",
        "reservation": "notif_reservations", "collaboration": "notif_collaborations",
        "interaction": "notif_interactions", "abonnement": "notif_abonnes"
    }.get(type_)
    if preference and getattr(u, preference, True) is False:
        return
    db.session.add(Notification(destinataire_id=destinataire_id, type=type_, titre=titre, contenu=contenu, lien=lien))


def rechercher_photographes(mot_cle="", ville="", type_prestation=""):
    query = Utilisateur.query.join(ProfilPhotographe).filter(Utilisateur.role == "photographe")

    if mot_cle:
        motif = f"%{mot_cle}%"
        query = query.filter(
            db.or_(
                Utilisateur.nom.ilike(motif),
                Utilisateur.ville.ilike(motif),
                ProfilPhotographe.specialites.ilike(motif),
                ProfilPhotographe.presentation.ilike(motif),
            )
        )
    if ville:
        query = query.filter(Utilisateur.ville.ilike(f"%{ville}%"))
    if type_prestation:
        query = query.filter(ProfilPhotographe.specialites.ilike(f"%{type_prestation}%"))

    return query.all()


@app.route("/")
def accueil():
    mot_cle = request.args.get("q", "").strip()
    ville = request.args.get("ville", "").strip()
    type_prestation = request.args.get("type", "").strip()
    recherche_photos = []
    resultats_recherche = []
    a_recherche = bool(mot_cle or ville or type_prestation)

    if a_recherche:
        resultats_recherche = rechercher_photographes(mot_cle, ville, type_prestation)
        q = f"%{mot_cle}%" if mot_cle else "%"
        recherche_photos = (Publication.query.join(Utilisateur, Publication.utilisateur_id == Utilisateur.id)
            .filter((Publication.legende.ilike(q)) | (Utilisateur.nom.ilike(q)))
            .order_by(Publication.created_at.desc()).limit(12).all())

    photographes_a_decouvrir = (Utilisateur.query.join(ProfilPhotographe)
        .filter(Utilisateur.role == "photographe", ProfilPhotographe.visibilite_pro.is_(True))
        .order_by(ProfilPhotographe.note_moyenne.desc()).limit(6).all())
    publications = Publication.query.order_by(Publication.created_at.desc()).limit(12).all()

    return render_template("index.html", mot_cle=mot_cle, ville=ville, type_prestation=type_prestation,
        a_recherche=a_recherche, resultats_recherche=resultats_recherche, recherche_photos=recherche_photos,
        photographes_a_decouvrir=photographes_a_decouvrir, publications=publications)


@app.route("/photographes", methods=["GET"])
def photographes():
    mot_cle = request.args.get("q", "").strip()
    ville = request.args.get("ville", "").strip()
    type_prestation = request.args.get("type", "").strip()
    resultats = rechercher_photographes(mot_cle, ville, type_prestation)
    return render_template("photographes.html", mot_cle=mot_cle, ville=ville, type_prestation=type_prestation, resultats=resultats)


@app.route("/comment-ca-marche")
def comment_ca_marche():
    return render_template("comment_ca_marche.html")


@app.route("/formations")
def formations():
    """Espace de formations réservé aux photographes inscrits."""
    utilisateur = Utilisateur.query.get(session.get("utilisateur_id")) if session.get("utilisateur_id") else None
    if utilisateur is None:
        return redirect(url_for("connexion", next=url_for("formations")))
    if utilisateur.role != "photographe":
        flash("Cette page est réservée aux photographes.", "error")
        return redirect(url_for("accueil"))
    return render_template("formations.html")


@app.route("/cgu")
def cgu():
    return render_template("page_legale.html", titre="Conditions d'utilisation")


@app.route("/confidentialite")
def confidentialite():
    return render_template("page_legale.html", titre="Politique de confidentialité")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/photographe/<int:photographe_id>/devis", methods=["GET", "POST"])
def demander_devis(photographe_id):
    photographe = Utilisateur.query.filter_by(id=photographe_id, role="photographe").first()
    if photographe is None:
        return "Photographe introuvable", 404

    if "utilisateur_id" not in session:
        return redirect(url_for("connexion", next=url_for("demander_devis", photographe_id=photographe_id)))

    client = Utilisateur.query.get(session["utilisateur_id"])
    if client is None:
        session.pop("utilisateur_id", None)
        return redirect(url_for("connexion", next=url_for("demander_devis", photographe_id=photographe_id)))
    if client.role != "client":
        return render_template("devis.html", photographe=photographe, message="Seuls les comptes client peuvent demander un devis.", current_date=date.today().isoformat(), max_date=date(date.today().year + 2, 12, 31).isoformat())

    if request.method == "POST":
        reservation = Reservation(
            client_id=client.id,
            photographe_id=photographe.id,
            type_prestation=request.form.get("type_prestation", "").strip(),
            date_prestation=request.form.get("date_prestation", "").strip(),
            budget=request.form.get("budget", type=int),
            message=request.form.get("message", "").strip(),
        )
        db.session.add(reservation)
        db.session.flush()
        creer_notification(photographe.id, "demande", "Nouvelle demande de prestation",
            f"{client.nom} souhaite travailler avec vous.", url_for("mes_demandes"))
        db.session.commit()
        return render_template("devis.html", photographe=photographe, message="Ta demande a bien été envoyée au photographe.", current_date=date.today().isoformat(), max_date=date(date.today().year + 2, 12, 31).isoformat())

    return render_template("devis.html", photographe=photographe, current_date=date.today().isoformat(), max_date=date(date.today().year + 2, 12, 31).isoformat())


@app.route("/photographe/<int:photographe_id>/avis", methods=["POST"])
def laisser_avis(photographe_id):
    photographe = Utilisateur.query.filter_by(id=photographe_id, role="photographe").first()
    if photographe is None:
        return "Photographe introuvable", 404

    if "utilisateur_id" not in session:
        return redirect(url_for("connexion", next=url_for("profil_photographe", photographe_id=photographe_id)))

    client = Utilisateur.query.get(session["utilisateur_id"])
    if client is None:
        session.pop("utilisateur_id", None)
        return redirect(url_for("connexion", next=url_for("profil_photographe", photographe_id=photographe_id)))

    if client.role == "client":
        avis = Avis(
            client_id=client.id,
            photographe_id=photographe.id,
            note=request.form.get("note", 5, type=int),
            commentaire=request.form.get("commentaire", "").strip(),
        )
        db.session.add(avis)
        db.session.flush()

        # Recalcule la note moyenne du photographe
        tous_les_avis = Avis.query.filter_by(photographe_id=photographe.id).all()
        photographe.profil_photographe.note_moyenne = round(
            sum(a.note for a in tous_les_avis) / len(tous_les_avis), 1
        )
        db.session.commit()

    return redirect(url_for("profil_photographe", photographe_id=photographe_id))


@app.route("/photographe/<int:photographe_id>")
def profil_photographe(photographe_id):
    photographe = Utilisateur.query.filter_by(id=photographe_id, role="photographe").first()
    if photographe is None:
        return "Photographe introuvable", 404
    avis_liste = Avis.query.filter_by(photographe_id=photographe_id).order_by(Avis.created_at.desc()).all()
    albums = Album.query.filter_by(photographe_id=photographe.id, publication_visible=True).order_by(Album.created_at.desc()).all()
    return render_template("profil.html", photographe=photographe, albums=albums, avis_liste=avis_liste, reposts=Repost.query.filter_by(utilisateur_id=photographe.id).order_by(Repost.created_at.desc()).all())


@app.route("/mon-profil/avatar", methods=["POST"])
def modifier_avatar():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))
    utilisateur = Utilisateur.query.get(session["utilisateur_id"])
    if utilisateur is None:
        session.pop("utilisateur_id", None)
        return redirect(url_for("connexion"))
    fichier = request.files.get("avatar")
    nouvel_avatar = enregistrer_image(fichier)
    if not nouvel_avatar:
        flash("Choisissez une image JPG, JPEG, PNG ou WEBP valide.", "error")
    else:
        ancien_avatar = utilisateur.avatar_url
        utilisateur.avatar_url = nouvel_avatar
        db.session.commit()
        if ancien_avatar and "/uploads/" in ancien_avatar:
            supprimer_fichier_upload(ancien_avatar)
        flash("Photo de profil mise à jour.", "success")
    return redirect(url_for("mon_profil"))

@app.route("/mon-profil/modifier", methods=["GET", "POST"])
def modifier_profil():
    # Ancienne URL conservée pour les liens déjà présents : l'édition se fait désormais
    # directement dans la rubrique « Modifier le profil » des paramètres.
    return redirect(url_for("parametres", section="profil"))

def supprimer_fichier_upload(url_image):
    """Supprime le fichier physique correspondant à une URL d'image uploadée (best-effort)."""
    if not url_image:
        return
    nom_fichier = url_image.rsplit("/", 1)[-1]
    chemin = os.path.join(app.config["UPLOAD_FOLDER"], nom_fichier)
    if os.path.exists(chemin):
        os.remove(chemin)


@app.route("/album/<int:album_id>/supprimer", methods=["POST"])
def supprimer_album(album_id):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    album = Album.query.get(album_id)
    if album is None or album.photographe_id != session["utilisateur_id"]:
        return "Non autorisé", 403

    for photo in album.photos:
        supprimer_fichier_upload(photo.image_url)
    publication = Publication.query.filter_by(album_id=album.id).first()
    if publication:
        db.session.delete(publication)
    db.session.delete(album)  # supprime aussi les photos liées (cascade)
    db.session.commit()
    return redirect(url_for("mon_profil"))


@app.route("/photo/<int:photo_id>/supprimer", methods=["POST"])
def supprimer_photo(photo_id):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    photo = PortfolioPhoto.query.get(photo_id)
    if photo is None or photo.album.photographe_id != session["utilisateur_id"]:
        return "Non autorisé", 403

    album_id = photo.album_id
    supprimer_fichier_upload(photo.image_url)
    db.session.delete(photo)
    db.session.commit()
    return redirect(url_for("voir_album", album_id=album_id))


@app.route("/mon-profil/albums/nouveau", methods=["POST"])
def creer_album():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    utilisateur = Utilisateur.query.get(session["utilisateur_id"])
    if utilisateur is None or utilisateur.role != "photographe":
        session.pop("utilisateur_id", None)
        return redirect(url_for("connexion"))

    titre = request.form.get("titre", "").strip()
    categorie = request.form.get("categorie", "").strip()
    fichiers = request.files.getlist("photos")
    client_id = request.form.get("client_id", type=int)
    reservation_id = request.form.get("reservation_id", type=int)
    politique = request.form.get("politique_telechargement", "client")
    if client_id is None and reservation_id:
        r = Reservation.query.get(reservation_id)
        client_id = r.client_id if r and r.photographe_id == utilisateur.id else None

    if titre and fichiers:
        album = Album(photographe_id=utilisateur.id, client_id=client_id, reservation_id=reservation_id, titre=titre, categorie=categorie, politique_telechargement=politique)
        db.session.add(album)
        db.session.flush()  # pour obtenir album.id

        for fichier in fichiers:
            url_image = enregistrer_image(fichier)
            if url_image:
                db.session.add(PortfolioPhoto(album_id=album.id, image_url=url_image))

        db.session.flush()
        if album.photos:
            db.session.add(Publication(utilisateur_id=utilisateur.id, image_url=album.photos[0].image_url, legende=titre, album_id=album.id))
        db.session.flush()
        if client_id and client_id != utilisateur.id:
            creer_notification(client_id, "collaboration", "Nouvel album photo à valider",
                f"{utilisateur.nom} vous a identifié(e) dans l’album « {titre} ». Validez-le pour l’afficher sur votre profil.",
                url_for("voir_album", album_id=album.id))
        db.session.commit()

    return redirect(url_for("mon_profil"))


@app.route("/album/<int:album_id>")
def voir_album(album_id):
    album = Album.query.get(album_id)
    if album is None:
        return "Album introuvable", 404
    return render_template("album.html", album=album)


@app.route("/mes-demandes")
def mes_demandes():
    if "utilisateur_id" not in session: return redirect(url_for("connexion"))
    u=Utilisateur.query.get(session["utilisateur_id"])
    if not u: return redirect(url_for("connexion"))
    filtre=request.args.get("statut","toutes")
    query=Reservation.query.filter_by(photographe_id=u.id) if u.role=="photographe" else Reservation.query.filter_by(client_id=u.id)
    if filtre!="toutes": query=query.filter_by(statut=filtre)
    demandes=query.order_by(Reservation.created_at.desc()).all()
    return render_template("mes_demandes.html", demandes=demandes, filtre=filtre, role=u.role)

@app.route("/demande/<int:reservation_id>/statut", methods=["POST"])
def modifier_statut_demande(reservation_id):
    if "utilisateur_id" not in session: return redirect(url_for("connexion"))
    utilisateur=Utilisateur.query.get(session["utilisateur_id"]); demande=Reservation.query.get_or_404(reservation_id)
    statut=request.form.get("statut","").strip()
    if utilisateur.role=="photographe" and demande.photographe_id==utilisateur.id and statut in {"en_attente","discussion","acceptee","refusee","terminee"}:
        demande.statut=statut
    elif utilisateur.role=="client" and demande.client_id==utilisateur.id and statut=="acceptee" and demande.devis is not None:
        demande.statut="acceptee"
    else: return "Non autorisé",403
    creer_notification(
        demande.client_id if utilisateur.role == "photographe" else demande.photographe_id,
        "reservation", "Mise à jour de votre demande",
        f"Le statut est maintenant : {demande.statut.replace('_',' ')}.", url_for("mes_demandes")
    )
    db.session.commit(); return redirect(request.referrer or url_for("mes_demandes"))

@app.route("/demande/<int:reservation_id>/devis", methods=["POST"])
def envoyer_devis(reservation_id):
    if "utilisateur_id" not in session: return redirect(url_for("connexion"))
    u=Utilisateur.query.get(session["utilisateur_id"]); d=Reservation.query.get_or_404(reservation_id)
    if not u or u.role!="photographe" or d.photographe_id!=u.id: return "Non autorisé",403
    montant=request.form.get("devis",type=int)
    if montant and montant>0:
        d.devis=montant; d.statut="discussion"; db.session.commit()
    return redirect(request.referrer or url_for("mes_demandes"))


@app.route("/mon-profil")
def mon_profil():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))
    utilisateur = Utilisateur.query.get(session["utilisateur_id"])
    if utilisateur is None:
        session.pop("utilisateur_id", None)
        return redirect(url_for("connexion"))
    publications = Publication.query.filter_by(utilisateur_id=utilisateur.id).order_by(Publication.created_at.desc()).all()
    if utilisateur.role == "client":
        collab_pubs = (Publication.query.join(Album, Publication.album_id == Album.id)
            .filter(Album.client_id == utilisateur.id, Album.collaboration_acceptee.is_(True), Album.publication_visible.is_(True))
            .order_by(Publication.created_at.desc()).all())
        publications = sorted(publications + [p for p in collab_pubs if p not in publications], key=lambda p: p.created_at, reverse=True)
    reposts = Repost.query.filter_by(utilisateur_id=utilisateur.id).order_by(Repost.created_at.desc()).all()
    enregistrements = Enregistrement.query.filter_by(utilisateur_id=utilisateur.id).order_by(Enregistrement.created_at.desc()).all()
    if utilisateur.role == "photographe":
        demandes = Reservation.query.filter_by(photographe_id=utilisateur.id).order_by(Reservation.created_at.desc()).all()
        albums = Album.query.filter_by(photographe_id=utilisateur.id).order_by(Album.created_at.desc()).all()
        return render_template("mon_profil_photographe.html", utilisateur=utilisateur, albums=albums,
            reposts=reposts, enregistrements=enregistrements, demandes_en_cours=[r for r in demandes if r.statut in ("en_attente", "discussion")],
            prochaines_prestations=[r for r in demandes if r.statut == "acceptee"],
            dernieres_prestations=[r for r in demandes if r.statut in ("acceptee", "terminee")][:5])
    reservations = Reservation.query.filter_by(client_id=utilisateur.id).order_by(Reservation.created_at.desc()).all()
    albums = Album.query.filter_by(client_id=utilisateur.id, collaboration_acceptee=True, publication_visible=True).order_by(Album.created_at.desc()).all()
    return render_template("mon_profil_client.html", utilisateur=utilisateur, albums=albums,
        reposts=reposts, enregistrements=enregistrements, prochaines_seances=[r for r in reservations if r.statut == "acceptee"],
        demandes_en_cours=[r for r in reservations if r.statut in ("en_attente", "discussion")], dernieres_reservations=reservations[:5])


@app.route("/client/<int:client_id>")
def profil_client(client_id):
    profil = Utilisateur.query.filter_by(id=client_id, role="client").first()
    if profil is None or not profil.profil_public:
        return "Profil introuvable", 404
    albums = Album.query.filter_by(client_id=profil.id, collaboration_acceptee=True, publication_visible=True).order_by(Album.created_at.desc()).all()
    return render_template("profil_client_public.html", profil=profil, albums=albums,
        reposts=Repost.query.filter_by(utilisateur_id=profil.id).order_by(Repost.created_at.desc()).all())


@app.route("/api/utilisateurs/recherche")
def rechercher_utilisateurs_api():
    """Recherche universelle de personnes sur InstaShoot depuis la messagerie."""
    if "utilisateur_id" not in session:
        return jsonify([])

    moi = Utilisateur.query.get(session["utilisateur_id"])
    if not moi:
        return jsonify([])

    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    motif = f"%{q}%"
    filtres = [
        Utilisateur.nom.ilike(motif),
        Utilisateur.ville.ilike(motif),
    ]

    # Les spécialités/presentation existent uniquement pour les photographes.
    # On passe par une jointure externe pour permettre la recherche de tout le monde.
    resultats = (
        Utilisateur.query
        .outerjoin(ProfilPhotographe)
        .filter(Utilisateur.id != moi.id)
        .filter(Utilisateur.profil_public.is_(True))
        .filter(db.or_(
            *filtres,
            ProfilPhotographe.specialites.ilike(motif),
            ProfilPhotographe.presentation.ilike(motif),
        ))
        .order_by(Utilisateur.nom.asc())
        .limit(12)
        .all()
    )

    return jsonify([
        {
            "id": u.id,
            "nom": u.nom,
            "role": u.role,
            "role_label": "Photographe" if u.role == "photographe" else "Client",
            "ville": u.ville or "",
            "avatar_url": u.avatar_url or "",
            "url": url_for("profil_photographe", photographe_id=u.id)
                if u.role == "photographe"
                else url_for("profil_client", client_id=u.id),
        }
        for u in resultats
    ])

# Compatibilité avec d'anciens scripts/URLs.
@app.route("/api/clients/recherche")
def rechercher_clients_api():
    return rechercher_utilisateurs_api()


@app.route("/mon-profil/publier", methods=["POST"])
def publier_photo_client():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    utilisateur = Utilisateur.query.get(session["utilisateur_id"])
    if utilisateur is None:
        session.pop("utilisateur_id", None)
        return redirect(url_for("connexion"))

    # Les clients ne publient plus directement : les photos apparaissent via les albums
    # partagés par un photographe après validation.
    return redirect(url_for("mon_profil"))


@app.route("/mon-profil/publier-photographe", methods=["POST"])
def publier_photo_photographe():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))
    utilisateur = Utilisateur.query.get(session["utilisateur_id"])
    if utilisateur is None or utilisateur.role != "photographe":
        return "Non autorisé", 403
    # Les photographes publient désormais des albums, pas des photos isolées.
    return redirect(url_for("mon_profil"))


@app.route("/publication/<int:publication_id>/supprimer", methods=["POST"])
def supprimer_publication(publication_id):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))
    publication = Publication.query.get_or_404(publication_id)
    if publication.utilisateur_id != session["utilisateur_id"]:
        return "Non autorisé", 403
    supprimer_fichier_upload(publication.image_url)
    db.session.delete(publication)
    db.session.commit()
    return redirect(request.referrer or url_for("mon_profil"))


@app.route("/utilisateur/<int:utilisateur_id>/suivre", methods=["POST"])
def suivre(utilisateur_id):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    mon_id = session["utilisateur_id"]
    if mon_id != utilisateur_id and not Abonnement.query.filter_by(abonne_id=mon_id, suivi_id=utilisateur_id).first():
        db.session.add(Abonnement(abonne_id=mon_id, suivi_id=utilisateur_id))
        suiveur = Utilisateur.query.get(mon_id)
        creer_notification(utilisateur_id, "abonnement", "Nouvel abonné", f"{suiveur.nom} a commencé à vous suivre.", url_for("profil", utilisateur_id=mon_id) if False else url_for("mon_profil"))
        db.session.commit()

    return redirect(request.referrer or url_for("accueil"))


@app.route("/utilisateur/<int:utilisateur_id>/ne-plus-suivre", methods=["POST"])
def ne_plus_suivre(utilisateur_id):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    lien = Abonnement.query.filter_by(abonne_id=session["utilisateur_id"], suivi_id=utilisateur_id).first()
    if lien:
        db.session.delete(lien)
        db.session.commit()

    return redirect(request.referrer or url_for("accueil"))



@app.route("/publication/<int:publication_id>/like", methods=["POST"])
def liker_publication(publication_id):
    if "utilisateur_id" not in session: return jsonify({"ok":False,"message":"Connexion requise"}), 401
    uid=session["utilisateur_id"]; pub=Publication.query.get_or_404(publication_id)
    like=PublicationLike.query.filter_by(publication_id=pub.id, utilisateur_id=uid).first()
    if like: db.session.delete(like); liked=False
    else:
        db.session.add(PublicationLike(publication_id=pub.id, utilisateur_id=uid)); liked=True
        if pub.utilisateur_id != uid:
            creer_notification(pub.utilisateur_id, "interaction", "Votre album a reçu un J’aime", f"{Utilisateur.query.get(uid).nom} a aimé votre album « {pub.legende or 'Sans titre'} ».", url_for("voir_album", album_id=pub.album_id) if pub.album_id else url_for("voir_publication", publication_id=pub.id))
    db.session.commit()
    return jsonify({"ok":True,"liked":liked,"count":pub.nb_likes()}) if request.headers.get("X-Requested-With")=="XMLHttpRequest" else redirect(request.referrer or url_for("accueil"))

@app.route("/publication/<int:publication_id>/enregistrer", methods=["POST"])
def enregistrer_publication(publication_id):
    if "utilisateur_id" not in session: return jsonify({"ok":False,"message":"Connexion requise"}), 401
    uid=session["utilisateur_id"]; pub=Publication.query.get_or_404(publication_id)
    item=Enregistrement.query.filter_by(publication_id=pub.id, utilisateur_id=uid).first()
    if item: db.session.delete(item); saved=False
    else: db.session.add(Enregistrement(publication_id=pub.id, utilisateur_id=uid)); saved=True
    db.session.commit()
    return jsonify({"ok":True,"saved":saved}) if request.headers.get("X-Requested-With")=="XMLHttpRequest" else redirect(request.referrer or url_for("accueil"))

@app.route("/publication/<int:publication_id>/reposter", methods=["POST"])
def reposter_publication(publication_id):
    if "utilisateur_id" not in session: return jsonify({"ok":False,"message":"Connexion requise"}), 401
    uid=session["utilisateur_id"]; pub=Publication.query.get_or_404(publication_id)
    item=Repost.query.filter_by(publication_id=pub.id, utilisateur_id=uid).first()
    if item: db.session.delete(item); reposted=False
    else: db.session.add(Repost(publication_id=pub.id, utilisateur_id=uid)); reposted=True
    db.session.commit()
    return jsonify({"ok":True,"reposted":reposted,"count":pub.nb_reposts()}) if request.headers.get("X-Requested-With")=="XMLHttpRequest" else redirect(request.referrer or url_for("accueil"))

@app.route("/publication/<int:publication_id>/commenter", methods=["POST"])
def commenter_publication(publication_id):
    if "utilisateur_id" not in session: return jsonify({"ok":False,"message":"Connexion requise"}), 401
    contenu=request.form.get("contenu", "").strip()
    pub=Publication.query.get_or_404(publication_id)
    if contenu and (pub.auteur.commentaires_autorises or pub.utilisateur_id == session["utilisateur_id"]):
        c=Commentaire(publication_id=pub.id, utilisateur_id=session["utilisateur_id"], contenu=contenu)
        db.session.add(c)
        if pub.utilisateur_id != session["utilisateur_id"]:
            auteur_commentaire=Utilisateur.query.get(session["utilisateur_id"])
            creer_notification(pub.utilisateur_id, "interaction", "Nouveau commentaire", f"{auteur_commentaire.nom} a commenté votre album.", url_for("voir_album", album_id=pub.album_id) if pub.album_id else url_for("voir_publication", publication_id=pub.id))
        db.session.commit()
        payload={"ok":True,"count":pub.nb_commentaires(),"author":c.utilisateur.nom,"content":c.contenu}
        return jsonify(payload) if request.headers.get("X-Requested-With")=="XMLHttpRequest" else redirect(request.referrer or url_for("accueil"))
    return jsonify({"ok":False,"message":"Commentaire non autorisé."}), 403

@app.route("/publication/<int:publication_id>")
def voir_publication(publication_id):
    pub = Publication.query.get_or_404(publication_id)
    return render_template("publication.html", publication=pub)

@app.route("/mon-profil/supprimer", methods=["POST"])
def supprimer_compte():
    if "utilisateur_id" not in session: return redirect(url_for("connexion"))
    u=Utilisateur.query.get(session["utilisateur_id"])
    if not u: return redirect(url_for("accueil"))
    db.session.delete(u); db.session.commit(); session.clear(); return redirect(url_for("accueil"))

@app.route("/mon-profil/parametres", methods=["GET", "POST"])
def parametres():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))
    u = Utilisateur.query.get(session["utilisateur_id"])
    if u is None:
        session.pop("utilisateur_id", None)
        return redirect(url_for("connexion"))

    section = request.args.get("section", "compte")
    sections_valides = {"compte", "confidentialite", "notifications", "professionnel", "securite", "profil"}
    if section not in sections_valides or (section == "professionnel" and u.role != "photographe"):
        section = "compte"

    if request.method == "POST":
        section = request.form.get("section", section)
        action = request.form.get("action", "")

        if action == "account_info":
            # La modale n'envoie qu'un champ à la fois : les autres valeurs sont conservées.
            if "email" in request.form:
                email = request.form.get("email", "").strip().lower()
                autre = Utilisateur.query.filter(Utilisateur.email == email, Utilisateur.id != u.id).first() if email else None
                if not email or autre:
                    flash("Cette adresse e-mail est déjà utilisée ou invalide.", "error")
                    return redirect(url_for("parametres", section="compte"))
                u.email = email
            if "telephone" in request.form:
                u.telephone = request.form.get("telephone", "").strip()
            if "ville" in request.form:
                u.ville = request.form.get("ville", "").strip()
            db.session.commit()
            flash("Informations du compte mises à jour.", "success")
            return redirect(url_for("parametres", section="compte"))

        if action == "profile_info":
            u.nom = request.form.get("nom", "").strip() or u.nom
            u.bio = request.form.get("bio", "").strip()
            fichier = request.files.get("avatar")
            nouvel_avatar = enregistrer_image(fichier)
            if nouvel_avatar:
                ancien_avatar = u.avatar_url
                u.avatar_url = nouvel_avatar
                if ancien_avatar and "/uploads/" in ancien_avatar:
                    supprimer_fichier_upload(ancien_avatar)
            if u.role == "photographe" and u.profil_photographe:
                p = u.profil_photographe
                p.presentation = request.form.get("presentation", "").strip()
                p.specialites = request.form.get("specialites", "").strip()
                p.annees_experience = request.form.get("annees_experience", 0, type=int)
                p.tarif_min = request.form.get("tarif_min", 0, type=int)
                p.reseaux_sociaux = request.form.get("reseaux_sociaux", "").strip()
            db.session.commit()
            flash("Votre profil a été mis à jour.", "success")
            return redirect(url_for("parametres", section="profil"))

        if section == "confidentialite":
            u.profil_public = request.form.get("profil_public") == "on"
            u.qui_peut_contacter = request.form.get("qui_peut_contacter", "tous")
            u.commentaires_autorises = request.form.get("commentaires_autorises") == "on"
            u.tags_autorises = request.form.get("tags_autorises") == "on"
            message = "Vos réglages de confidentialité ont été enregistrés."
        elif section == "notifications":
            for field in ["notif_messages", "notif_demandes", "notif_reservations", "notif_collaborations", "notif_interactions", "notif_abonnes"]:
                setattr(u, field, request.form.get(field) == "on")
            message = "Vos préférences de notification ont été enregistrées."
        elif section == "professionnel" and u.role == "photographe":
            u.profil_photographe.disponibilite = request.form.get("disponibilite", "").strip()
            u.profil_photographe.visibilite_pro = request.form.get("visibilite_pro") == "on"
            message = "Votre profil professionnel a été mis à jour."
        elif section == "securite":
            actuel = request.form.get("mot_de_passe_actuel", "")
            nouveau = request.form.get("nouveau_mot_de_passe", "")
            confirmation = request.form.get("confirmation_mot_de_passe", "")
            if not u.verifier_mot_de_passe(actuel):
                flash("Le mot de passe actuel est incorrect.", "error")
                return redirect(url_for("parametres", section="securite"))
            if len(nouveau) < 8:
                flash("Le nouveau mot de passe doit contenir au moins 8 caractères.", "error")
                return redirect(url_for("parametres", section="securite"))
            if nouveau != confirmation:
                flash("Les deux nouveaux mots de passe ne correspondent pas.", "error")
                return redirect(url_for("parametres", section="securite"))
            u.set_mot_de_passe(nouveau)
            message = "Votre mot de passe a été modifié."
        else:
            flash("Action non reconnue.", "error")
            return redirect(url_for("parametres", section="compte"))

        db.session.commit()
        flash(message, "success")
        return redirect(url_for("parametres", section=section))

    return render_template("parametres.html", utilisateur=u, section=section)

@app.route("/album/<int:album_id>/collaboration", methods=["POST"])
def gerer_collaboration(album_id):
    if "utilisateur_id" not in session: return redirect(url_for("connexion"))
    album=Album.query.get_or_404(album_id); uid=session["utilisateur_id"]
    if album.client_id != uid and album.photographe_id != uid: return "Non autorisé",403
    if album.client_id == uid:
        album.collaboration_acceptee=True
        Notification.query.filter_by(destinataire_id=uid, type="collaboration", lien=url_for("voir_album", album_id=album.id), lu=False).update({"lu": True}, synchronize_session=False)
        creer_notification(album.photographe_id, "collaboration", "Album approuvé",
            f"{album.client.nom} a approuvé l’album « {album.titre} ». Il apparaît maintenant sur son profil.",
            url_for("voir_album", album_id=album.id))
    if request.form.get("politique_telechargement") in ("client","tous","personne"):
        album.politique_telechargement=request.form["politique_telechargement"]
    db.session.commit(); return redirect(request.referrer or url_for("voir_album", album_id=album.id))

@app.route("/inspiration")
def inspiration():
    # Inspiration est un feed de PUBLICATIONS, jamais une liste de PortfolioPhoto.
    # Un album peut être attaché à une publication (et être présenté comme carousel),
    # mais ses photos ne deviennent pas des éléments indépendants du feed.
    publications = (
        Publication.query
        .join(Utilisateur, Publication.utilisateur_id == Utilisateur.id)
        .outerjoin(Album, Publication.album_id == Album.id)
        .filter(Utilisateur.role == "photographe")
        .filter(db.or_(Publication.album_id.is_(None), Album.publication_visible.is_(True)))
        .order_by(Publication.created_at.desc())
        .all()
    )
    return render_template("inspiration.html", publications=publications)


@app.route("/messages", methods=["GET", "POST"])
def messagerie():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))
    moi = Utilisateur.query.get(session["utilisateur_id"])
    if moi is None:
        session.pop("utilisateur_id", None)
        return redirect(url_for("connexion"))

    avec_id = request.args.get("avec", type=int)
    destinataire = Utilisateur.query.get(avec_id) if avec_id else None
    if destinataire and destinataire.id != moi.id:
        if destinataire.qui_peut_contacter == "personne" or (destinataire.qui_peut_contacter == "abonnes" and not destinataire.est_suivi_par(moi.id)):
            destinataire = None
    if request.method == "POST":
        destinataire_id = request.form.get("destinataire_id", type=int)
        contenu = request.form.get("contenu", "").strip()
        destinataire = Utilisateur.query.get(destinataire_id)
        if destinataire and destinataire.id != moi.id and contenu:
            db.session.add(Message(expediteur_id=moi.id, destinataire_id=destinataire.id, contenu=contenu))
            db.session.commit()
            return redirect(url_for("messagerie", avec=destinataire.id))

    conversations = {}
    messages = Message.query.filter(db.or_(Message.expediteur_id == moi.id, Message.destinataire_id == moi.id)).order_by(Message.created_at.asc()).all()
    for msg in messages:
        autre_id = msg.destinataire_id if msg.expediteur_id == moi.id else msg.expediteur_id
        conversations.setdefault(autre_id, []).append(msg)
    contacts = [Utilisateur.query.get(uid) for uid in conversations]
    contacts = [c for c in contacts if c]
    fil_conversation = conversations.get(destinataire.id, []) if destinataire else []
    for msg in fil_conversation:
        if msg.destinataire_id == moi.id and not msg.lu:
            msg.lu = True
    db.session.commit()
    return render_template("messagerie.html", contacts=contacts, destinataire=destinataire, conversation=fil_conversation, moi=moi)


@app.route("/notifications")
def notifications():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))
    moi = Utilisateur.query.get(session["utilisateur_id"])
    if not moi:
        session.clear(); return redirect(url_for("connexion"))
    items = Notification.query.filter_by(destinataire_id=moi.id).order_by(Notification.created_at.desc()).limit(60).all()
    return render_template("notifications.html", notifications=items, role=moi.role)


@app.route("/notifications/<int:notification_id>/lire", methods=["POST"])
def lire_notification(notification_id):
    if "utilisateur_id" not in session: return redirect(url_for("connexion"))
    n = Notification.query.filter_by(id=notification_id, destinataire_id=session["utilisateur_id"]).first_or_404()
    n.lu = True
    db.session.commit()
    return redirect(n.lien or url_for("notifications"))


@app.route("/notifications/lire-toutes", methods=["POST"])
def lire_toutes_notifications():
    if "utilisateur_id" not in session: return redirect(url_for("connexion"))
    Notification.query.filter_by(destinataire_id=session["utilisateur_id"], lu=False).update({"lu": True}, synchronize_session=False)
    db.session.commit()
    return redirect(url_for("notifications"))


@app.route("/devenir-photographe")
def devenir_photographe():
    return render_template("devenir_photographe.html")


@app.route("/inscription-ajax", methods=["POST"])
def inscription_ajax():
    role = request.form.get("role", "client")
    email = request.form.get("email", "").strip().lower()

    if Utilisateur.query.filter_by(email=email).first():
        return {"ok": False, "message": "Un compte existe déjà avec cet email."}, 400

    u = Utilisateur(
        role=role,
        nom=request.form.get("nom", "").strip(),
        email=email,
        telephone=request.form.get("telephone", "").strip(),
        ville=request.form.get("ville", "").strip(),
    )
    u.set_mot_de_passe(request.form.get("mot_de_passe", ""))
    db.session.add(u)
    db.session.flush()

    if role == "photographe":
        profil = ProfilPhotographe(
            id=u.id,
            specialites=request.form.get("specialites", "").strip(),
            presentation=request.form.get("presentation", "").strip(),
            annees_experience=request.form.get("annees_experience", 0, type=int),
            tarif_min=request.form.get("tarif_min", 0, type=int),
            reseaux_sociaux=request.form.get("reseaux_sociaux", "").strip(),
        )
        db.session.add(profil)

    db.session.commit()
    session["utilisateur_id"] = u.id
    envoyer_email_bienvenue_async(u)
    return {"ok": True}


@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    role = request.values.get("role", "client")
    if request.method == "POST":
        role = request.form.get("role", "client")
        email = request.form.get("email", "").strip().lower()

        if Utilisateur.query.filter_by(email=email).first():
            return render_template("inscription.html", role=role, message="Un compte existe déjà avec cet email.")

        u = Utilisateur(
            role=role,
            nom=request.form.get("nom", "").strip(),
            email=email,
            telephone=request.form.get("telephone", "").strip(),
            ville=request.form.get("ville", "").strip(),
        )
        u.set_mot_de_passe(request.form.get("mot_de_passe", ""))
        db.session.add(u)
        db.session.flush()

        if role == "photographe":
            profil = ProfilPhotographe(
                id=u.id,
                specialites=request.form.get("specialites", "").strip(),
                presentation=request.form.get("presentation", "").strip(),
                annees_experience=request.form.get("annees_experience", 0, type=int),
                tarif_min=request.form.get("tarif_min", 0, type=int),
                reseaux_sociaux=request.form.get("reseaux_sociaux", "").strip(),
            )
            db.session.add(profil)

        db.session.commit()
        session["utilisateur_id"] = u.id
        envoyer_email_bienvenue_async(u)
        return redirect(url_for("accueil"))

    return render_template("inscription.html", role=role)


def envoyer_email_gmail(email_destinataire, sujet, contenu):
    """Envoie un e-mail via le compte Gmail officiel d'InstaShoot."""
    expediteur = app.config.get("MAIL_USERNAME", "").strip()
    mot_de_passe = app.config.get("MAIL_PASSWORD", "").replace(" ", "").strip()
    email_destinataire = (email_destinataire or "").strip().lower()

    if not expediteur or not mot_de_passe or not email_destinataire:
        app.logger.error("Gmail non configuré ou adresse destinataire manquante.")
        return False

    message = EmailMessage()
    message["Subject"] = sujet
    # Affiche clairement le nom du service tout en conservant l'adresse support.
    message["From"] = formataddr(("InstaShoot", expediteur))
    message["To"] = email_destinataire
    message["Reply-To"] = expediteur
    message.set_content(contenu)

    try:
        with smtplib.SMTP_SSL(
            app.config["MAIL_SERVER"],
            app.config["MAIL_PORT"],
            timeout=15
        ) as serveur:
            serveur.login(expediteur, mot_de_passe)
            serveur.send_message(message)
        return True
    except Exception:
        app.logger.exception("Échec de l'envoi d'un e-mail Gmail.")
        return False


def envoyer_email_bienvenue(email, prenom=""):
    """Envoie un message de bienvenue après une connexion réussie.
    N'utilise que des valeurs déjà extraites (pas d'objet SQLAlchemy) car
    cette fonction est appelée depuis un thread séparé de la requête.
    """
    prenom = (prenom or "").strip()
    nom_affiche = f" {prenom}" if prenom else ""

    contenu = f"""Bonjour{nom_affiche},

Bienvenue sur InstaShoot !

Votre connexion à votre compte InstaShoot vient d'être effectuée avec succès.

Vous pouvez maintenant découvrir des photographes, présenter votre travail, échanger avec la communauté et profiter pleinement de votre espace.

Si vous n'êtes pas à l'origine de cette connexion, nous vous recommandons de vérifier votre compte et de modifier votre mot de passe.

À très bientôt sur InstaShoot !

L'équipe InstaShoot
"""
    return envoyer_email_gmail(
        email,
        "Bienvenue sur InstaShoot 👋",
        contenu
    )


def envoyer_email_bienvenue_async(utilisateur):
    """Lance l'envoi de l'email de bienvenue dans un thread séparé pour ne
    jamais ralentir la réponse de connexion (le SMTP Gmail peut prendre
    plusieurs secondes, voire expirer)."""
    email = utilisateur.email
    prenom = utilisateur.nom
    threading.Thread(
        target=envoyer_email_bienvenue, args=(email, prenom), daemon=True
    ).start()


def envoyer_code_reinitialisation(email_destinataire, code):
    """Envoie le code de récupération par Gmail."""
    contenu = f"""Bonjour,

Vous avez demandé à réinitialiser votre mot de passe InstaShoot.

Votre code de vérification est : {code}

Ce code est valable pendant 10 minutes et ne peut être utilisé qu'une seule fois.

Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet e-mail.

L'équipe InstaShoot
"""
    return envoyer_email_gmail(
        email_destinataire,
        "InstaShoot — Code de réinitialisation",
        contenu
    )


def creer_code_reinitialisation(utilisateur):
    """Crée un code à 6 chiffres, stocké uniquement sous forme hachée."""
    # Invalide les anciennes demandes encore actives.
    DemandeReinitialisationMotDePasse.query.filter_by(
        utilisateur_id=utilisateur.id, utilise=False
    ).delete(synchronize_session=False)

    code = f"{secrets.randbelow(1000000):06d}"
    demande = DemandeReinitialisationMotDePasse(
        utilisateur_id=utilisateur.id,
        code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
        expire_at=datetime.utcnow() + timedelta(minutes=app.config["RESET_CODE_EXPIRATION_MINUTES"]),
        tentatives=0,
        utilise=False,
    )
    db.session.add(demande)
    db.session.commit()
    return code


@app.route("/mot-de-passe-oublie", methods=["GET", "POST"])
def mot_de_passe_oublie():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        utilisateur = Utilisateur.query.filter_by(email=email).first() if email else None

        # Message identique dans tous les cas afin de ne pas révéler les comptes existants.
        message = "Si cette adresse est associée à un compte, un code de vérification vient d'être envoyé. Vérifiez votre boîte de réception et vos spams."
        if utilisateur:
            # Évite un envoi répété immédiat pour la même adresse.
            derniere = DemandeReinitialisationMotDePasse.query.filter_by(
                utilisateur_id=utilisateur.id, utilise=False
            ).order_by(DemandeReinitialisationMotDePasse.created_at.desc()).first()
            if derniere and (datetime.utcnow() - derniere.created_at).total_seconds() < app.config["RESET_RESEND_DELAY_SECONDS"]:
                flash("Un code vient déjà d'être envoyé. Attendez une minute avant d'en demander un nouveau.", "error")
                return render_template("mot_de_passe_oublie.html")

            code = creer_code_reinitialisation(utilisateur)
            if envoyer_code_reinitialisation(utilisateur.email, code):
                session.pop("reset_user_id", None)
            else:
                # Ne laisse pas un code actif si l'envoi a échoué.
                DemandeReinitialisationMotDePasse.query.filter_by(
                    utilisateur_id=utilisateur.id, utilise=False
                ).delete(synchronize_session=False)
                db.session.commit()
                flash("L'envoi de l'e-mail a échoué. Vérifiez la configuration Gmail du site puis réessayez.", "error")
                return render_template("mot_de_passe_oublie.html")

        return render_template("mot_de_passe_code.html", email=email, message=message)

    return render_template("mot_de_passe_oublie.html")


@app.route("/mot-de-passe-code", methods=["GET", "POST"])
def verifier_code_reinitialisation():
    email = request.values.get("email", "").strip().lower()
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        utilisateur = Utilisateur.query.filter_by(email=email).first() if email else None

        if not re.fullmatch(r"\d{6}", code):
            return render_template(
                "mot_de_passe_code.html",
                email=email,
                erreur="Entrez un code à 6 chiffres."
            )
        demande = None
        if utilisateur:
            demande = DemandeReinitialisationMotDePasse.query.filter_by(
                utilisateur_id=utilisateur.id, utilise=False
            ).order_by(DemandeReinitialisationMotDePasse.created_at.desc()).first()

        if not demande or datetime.utcnow() > demande.expire_at:
            if demande:
                demande.utilise = True
                db.session.commit()
            return render_template("mot_de_passe_code.html", email=email, erreur="Ce code est expiré ou invalide. Demandez un nouveau code.")

        if demande.tentatives >= app.config["RESET_MAX_ATTEMPTS"]:
            return render_template("mot_de_passe_code.html", email=email, erreur="Trop de tentatives. Demandez un nouveau code.")

        demande.tentatives += 1
        valide = secrets.compare_digest(
            demande.code_hash,
            hashlib.sha256(code.encode("utf-8")).hexdigest()
        )
        if not valide:
            db.session.commit()
            reste = max(0, app.config["RESET_MAX_ATTEMPTS"] - demande.tentatives)
            return render_template("mot_de_passe_code.html", email=email, erreur=f"Code incorrect. Il vous reste {reste} tentative(s).")

        # Le code est marqué utilisé immédiatement : la session autorise ensuite une seule réinitialisation.
        demande.utilise = True
        db.session.commit()
        session.pop("reset_user_id", None)
        session.pop("reset_authorized_at", None)
        session["reset_user_id"] = utilisateur.id
        session["reset_authorized_at"] = datetime.utcnow().isoformat()
        return redirect(url_for("reinitialiser_mot_de_passe"))

    return render_template("mot_de_passe_code.html", email=email)


@app.route("/annuler-reinitialisation-mot-de-passe")
def annuler_reinitialisation_mot_de_passe():
    session.pop("reset_user_id", None)
    session.pop("reset_authorized_at", None)
    return redirect(url_for("connexion"))


@app.route("/reinitialiser-mot-de-passe", methods=["GET", "POST"])
def reinitialiser_mot_de_passe():
    user_id = session.get("reset_user_id")
    authorized_at = session.get("reset_authorized_at")
    if not user_id or not authorized_at:
        return redirect(url_for("mot_de_passe_oublie"))

    try:
        if datetime.utcnow() - datetime.fromisoformat(authorized_at) > timedelta(minutes=10):
            session.pop("reset_user_id", None)
            session.pop("reset_authorized_at", None)
            flash("La session de réinitialisation a expiré. Demandez un nouveau code.", "error")
            return redirect(url_for("mot_de_passe_oublie"))
    except ValueError:
        session.pop("reset_user_id", None)
        session.pop("reset_authorized_at", None)
        return redirect(url_for("mot_de_passe_oublie"))

    utilisateur = Utilisateur.query.get(user_id)
    if not utilisateur:
        session.pop("reset_user_id", None)
        session.pop("reset_authorized_at", None)
        return redirect(url_for("mot_de_passe_oublie"))

    if request.method == "POST":
        nouveau = request.form.get("nouveau_mot_de_passe", "")
        confirmation = request.form.get("confirmation_mot_de_passe", "")
        if len(nouveau) < 8:
            return render_template("reinitialiser_mot_de_passe.html", erreur="Le nouveau mot de passe doit contenir au moins 8 caractères.")
        if nouveau != confirmation:
            return render_template("reinitialiser_mot_de_passe.html", erreur="Les deux mots de passe ne correspondent pas.")

        utilisateur.set_mot_de_passe(nouveau)
        db.session.commit()
        session.pop("reset_user_id", None)
        session.pop("reset_authorized_at", None)
        flash("Votre mot de passe a été réinitialisé avec succès. Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for("connexion"))

    return render_template("reinitialiser_mot_de_passe.html")


def redirection_sure(chemin):
    """N'autorise que les chemins internes (évite les redirections vers un autre site)."""
    return chemin and chemin.startswith("/") and not chemin.startswith("//")


@app.route("/connexion-ajax", methods=["POST"])
def connexion_ajax():
    email = request.form.get("email", "").strip().lower()
    mot_de_passe = request.form.get("mot_de_passe", "")
    u = Utilisateur.query.filter_by(email=email).first()

    if u is None or not u.verifier_mot_de_passe(mot_de_passe):
        return {"ok": False, "message": "Email ou mot de passe incorrect."}, 401

    session["utilisateur_id"] = u.id
    envoyer_email_bienvenue_async(u)
    return {"ok": True, "nom": u.nom}


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    next_url = request.values.get("next", "")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        mot_de_passe = request.form.get("mot_de_passe", "")
        u = Utilisateur.query.filter_by(email=email).first()

        if u is None or not u.verifier_mot_de_passe(mot_de_passe):
            return render_template("connexion.html", message="Email ou mot de passe incorrect.", next=next_url)

        session["utilisateur_id"] = u.id
        envoyer_email_bienvenue_async(u)
        return redirect(next_url if redirection_sure(next_url) else url_for("accueil"))

    return render_template("connexion.html", next=next_url)


@app.route("/deconnexion", methods=["GET", "POST"])
def deconnexion():
    session.pop("utilisateur_id", None)
    return redirect(url_for("accueil"))


@app.context_processor
def injecter_utilisateur_courant():
    """Rend l'utilisateur connecté disponible dans tous les templates (pour la navbar)."""
    utilisateur = None
    if "utilisateur_id" in session:
        utilisateur = Utilisateur.query.get(session["utilisateur_id"])
    non_lus_messages = 0
    notifications_non_lues = 0
    if utilisateur:
        non_lus_messages = Message.query.filter_by(destinataire_id=utilisateur.id, lu=False).count()
        notifications_non_lues = Notification.query.filter_by(destinataire_id=utilisateur.id, lu=False).count()
        notifications_recentes = Notification.query.filter_by(destinataire_id=utilisateur.id).order_by(Notification.created_at.desc()).limit(5).all()
    else:
        notifications_recentes = []
    return {"utilisateur_courant": utilisateur, "messages_non_lus": non_lus_messages, "notifications_non_lues": notifications_non_lues, "notifications_recentes": notifications_recentes}



def migrer_sqlite():
    """Ajoute les colonnes de la nouvelle version sans casser une base existante."""
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    with db.engine.begin() as conn:
        if "utilisateur" in tables:
            cols={c["name"] for c in insp.get_columns("utilisateur")}
            additions={"profil_public":"BOOLEAN DEFAULT 1","qui_peut_contacter":"VARCHAR(30) DEFAULT 'tous'","commentaires_autorises":"BOOLEAN DEFAULT 1","tags_autorises":"BOOLEAN DEFAULT 1","notif_messages":"BOOLEAN DEFAULT 1","notif_demandes":"BOOLEAN DEFAULT 1","notif_reservations":"BOOLEAN DEFAULT 1","notif_collaborations":"BOOLEAN DEFAULT 1","notif_interactions":"BOOLEAN DEFAULT 1","notif_abonnes":"BOOLEAN DEFAULT 1"}
            for c,t in additions.items():
                if c not in cols: conn.execute(text(f"ALTER TABLE utilisateur ADD COLUMN {c} {t}"))
        if "profil_photographe" in tables:
            cols={c["name"] for c in insp.get_columns("profil_photographe")}
            for c,t in {"disponibilite":"VARCHAR(255) DEFAULT 'Disponible sur demande'","visibilite_pro":"BOOLEAN DEFAULT 1"}.items():
                if c not in cols: conn.execute(text(f"ALTER TABLE profil_photographe ADD COLUMN {c} {t}"))
        if "reservation" in tables:
            cols={c["name"] for c in insp.get_columns("reservation")}
            if "devis" not in cols: conn.execute(text("ALTER TABLE reservation ADD COLUMN devis INTEGER"))
        if "album" in tables:
            cols={c["name"] for c in insp.get_columns("album")}
            additions={"client_id":"INTEGER","reservation_id":"INTEGER","politique_telechargement":"VARCHAR(20) DEFAULT 'client'","collaboration_acceptee":"BOOLEAN DEFAULT 0","publication_visible":"BOOLEAN DEFAULT 1"}
            for c,t in additions.items():
                if c not in cols: conn.execute(text(f"ALTER TABLE album ADD COLUMN {c} {t}"))
        if "publication" in tables:
            cols={c["name"] for c in insp.get_columns("publication")}
            if "album_id" not in cols: conn.execute(text("ALTER TABLE publication ADD COLUMN album_id INTEGER"))

with app.app_context():
    db.create_all()
    migrer_sqlite()
    db.create_all()
    seeder_donnees_demo()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
