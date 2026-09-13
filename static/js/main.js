// Point d'entrée JS du projet.

// ============================
// Modale d'inscription
// ============================
function ouvrirModalInscription(role) {
  const overlay = document.getElementById("modal-inscription-overlay");
  const erreur = document.getElementById("modal-inscription-erreur");
  if (erreur) {
    erreur.style.display = "none";
    erreur.textContent = "";
  }
  choisirRoleModal(role || "client");
  if (overlay) overlay.classList.add("ouvert");
}

function fermerModalInscription() {
  const overlay = document.getElementById("modal-inscription-overlay");
  if (overlay) overlay.classList.remove("ouvert");
}

function choisirRoleModal(role) {
  document.getElementById("modal-inscription-role").value = role;
  document.getElementById("modal-champs-photographe").style.display = role === "photographe" ? "block" : "none";
  document.getElementById("modal-role-client").classList.toggle("active", role === "client");
  document.getElementById("modal-role-photographe").classList.toggle("active", role === "photographe");
}

async function soumettreInscriptionModal(event) {
  event.preventDefault();
  const form = event.target;
  const erreur = document.getElementById("modal-inscription-erreur");

  const reponse = await fetch("/inscription-ajax", {
    method: "POST",
    body: new FormData(form),
  });
  const data = await reponse.json();

  if (data.ok) {
    window.location.reload();
  } else {
    if (erreur) {
      erreur.textContent = data.message || "Une erreur est survenue.";
      erreur.style.display = "block";
    }
  }
  return false;
}
let urlApresConnexionModal = null;

function ouvrirModalConnexion(urlApresConnexion) {
  urlApresConnexionModal = urlApresConnexion || null;
  const overlay = document.getElementById("modal-connexion-overlay");
  const erreur = document.getElementById("modal-connexion-erreur");
  if (erreur) {
    erreur.style.display = "none";
    erreur.textContent = "";
  }
  if (overlay) overlay.classList.add("ouvert");
}

function fermerModalConnexion() {
  const overlay = document.getElementById("modal-connexion-overlay");
  if (overlay) overlay.classList.remove("ouvert");
}

async function soumettreConnexionModal(event) {
  event.preventDefault();
  const form = event.target;
  const erreur = document.getElementById("modal-connexion-erreur");

  const reponse = await fetch("/connexion-ajax", {
    method: "POST",
    body: new FormData(form),
  });
  const data = await reponse.json();

  if (data.ok) {
    if (urlApresConnexionModal) {
      window.location.href = urlApresConnexionModal;
    } else {
      window.location.reload();
    }
  } else {
    if (erreur) {
      erreur.textContent = data.message || "Une erreur est survenue.";
      erreur.style.display = "block";
    }
  }
  return false;
}

// ============================
// Profil façon Instagram : onglets persistants dans l'URL
// ============================
function basculerOngletProfil(nom, boutonClique, pushUrl = true) {
  document.querySelectorAll(".ig-panel").forEach((panel) => {
    panel.style.display = "none";
  });
  document.querySelectorAll(".ig-tab").forEach((btn) => {
    btn.classList.remove("active");
  });

  const panel = document.getElementById("onglet-" + nom);
  if (panel) {
    panel.style.display = "block";
    panel.style.opacity = "0";
    requestAnimationFrame(() => { panel.style.opacity = "1"; });
  }
  if (boutonClique) boutonClique.classList.add("active");

  if (pushUrl) {
    const url = new URL(window.location.href);
    url.hash = nom;
    history.replaceState(null, "", url.toString());
  }
}

function initialiserOngletProfil() {
  const hash = window.location.hash.replace("#", "");
  const bouton = hash ? document.querySelector(`.ig-tab[data-tab="${hash}"]`) : null;
  if (bouton) basculerOngletProfil(hash, bouton, false);
}

function afficherFormPublication(input, formId) {
  const form = document.getElementById(formId);
  if (!form || !input.files.length) return;
  form.classList.add("visible");
  const trigger = form.previousElementSibling;
  if (trigger) trigger.classList.add("selected");
}

async function partagerPublication(id, url, auteur) {
  const data = {
    title: `Photo de ${auteur}`,
    text: `Découvrez cette photo sur InstaShoot`,
    url: url
  };

  try {
    if (navigator.share) {
      await navigator.share(data);
      return;
    }
  } catch (error) {
    if (error && error.name === "AbortError") return;
  }

  try {
    await navigator.clipboard.writeText(url);
    afficherToast("Lien de la photo copié.");
  } catch (error) {
    const champ = document.createElement("input");
    champ.value = url;
    document.body.appendChild(champ);
    champ.select();
    document.execCommand("copy");
    champ.remove();
    afficherToast("Lien de la photo copié.");
  }
}

function afficherToast(message) {
  let toast = document.getElementById("pc-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "pc-toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(window.pcToastTimer);
  window.pcToastTimer = setTimeout(() => toast.classList.remove("visible"), 2200);
}

document.addEventListener("DOMContentLoaded", initialiserOngletProfil);

// ============================
// Panneau de notifications (déroulant sous la cloche)
// ============================
function basculerPanneauNotifications(event) {
  event.stopPropagation();
  const panneau = document.getElementById("panneau-notifications");
  if (panneau) panneau.classList.toggle("ouvert");
}

document.addEventListener("click", (e) => {
  const panneau = document.getElementById("panneau-notifications");
  if (panneau && panneau.classList.contains("ouvert") && !panneau.contains(e.target) && e.target.id !== "bouton-notifications") {
    panneau.classList.remove("ouvert");
  }
});

// ============================
// Paramètres : modales et actions de compte
// ============================
function ouvrirModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.add('ouvert');
    document.body.classList.add('modal-open');
    const first = el.querySelector('input:not([type=hidden]), textarea, select');
    if (first) setTimeout(() => first.focus(), 80);
  }
}

function fermerModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('ouvert');
  if (!document.querySelector('.modal-overlay.ouvert')) document.body.classList.remove('modal-open');
}

function ouvrirModalCompte(type) {
  const title = document.getElementById('modal-compte-title');
  const label = document.getElementById('modal-compte-label');
  const input = document.getElementById('modal-compte-input');
  if (!title || !label || !input) return;
  const data = {
    email: {title:'Modifier l’adresse e-mail', label:'Adresse e-mail', name:'email', value:window.pcAccountEmail || '', type:'email', placeholder:'vous@exemple.com'},
    telephone: {title:'Modifier le numéro', label:'Numéro de téléphone', name:'telephone', value:window.pcAccountPhone || '', type:'tel', placeholder:'+229 …'},
    ville: {title:'Modifier la ville', label:'Ville', name:'ville', value:window.pcAccountCity || '', type:'text', placeholder:'Cotonou'}
  }[type];
  if (!data) return;
  title.textContent = data.title;
  label.textContent = data.label;
  input.name = data.name;
  input.value = data.value;
  input.type = data.type;
  input.placeholder = data.placeholder;
  input.classList.toggle('pc-phone', type === 'telephone');
  if (type === 'telephone') initialiserTelephonesInternationaux();
  input.required = type !== 'telephone' && type !== 'ville';
  ouvrirModal('modal-compte');
}

function ouvrirModalMotDePasse() { ouvrirModal('modal-mdp'); }
function ouvrirModalSuppression() { ouvrirModal('modal-suppression'); }
function ouvrirModalDeconnexion() { ouvrirModal('modal-deconnexion'); }

function previsualiserAvatarSettings(input) {
  const button = document.querySelector('.settings-avatar-button');
  if (!button || !input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = e => { button.innerHTML = `<img src="${e.target.result}" alt="Aperçu de la photo de profil">`; };
  reader.readAsDataURL(input.files[0]);
}

// Fermer les modales avec Échap.
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.ouvert').forEach(el => el.classList.remove('ouvert'));
    document.body.classList.remove('modal-open');
  }
});


function ouvrirModalSuppressionAlbum(action, titre) {
  const form = document.getElementById('album-delete-form');
  const desc = document.getElementById('album-delete-description');
  if (form) form.action = action;
  if (desc) desc.textContent = `« ${titre} » et toutes les photos qu’il contient seront supprimés définitivement.`;
  ouvrirModal('modal-suppression-album');
}

// ============================
// Albums : carrousel façon publication
// ============================
function etatCarousel(id) {
  const root = document.querySelector(`[data-carousel="${id}"]`);
  if (!root) return null;
  const slides = [...root.querySelectorAll('.pc-carousel-slide')];
  let index = slides.findIndex(s => s.classList.contains('active'));
  if (index < 0) index = 0;
  return {root, slides, index};
}

function allerPhotoAlbum(id, index) {
  const state = etatCarousel(id);
  if (!state || !state.slides.length) return;
  index = Math.max(0, Math.min(index, state.slides.length - 1));
  state.slides.forEach((s, i) => s.classList.toggle('active', i === index));
  state.root.querySelectorAll('.pc-carousel-dot').forEach((d, i) => d.classList.toggle('active', i === index));
  const counter = state.root.querySelector('.pc-carousel-count');
  if (counter) counter.textContent = `${index + 1} / ${state.slides.length}`;
}

function carouselAlbum(id, direction) {
  const state = etatCarousel(id);
  if (!state) return;
  let next = state.index + direction;
  if (next < 0) next = state.slides.length - 1;
  if (next >= state.slides.length) next = 0;
  allerPhotoAlbum(id, next);
}

// ============================
// Création d'album : upload moderne + recherche client
// ============================
let albumUploadInitialised = false;
function initialiserUploadAlbum() {
  if (albumUploadInitialised) return;
  const input = document.getElementById('album-files-input');
  const zone = document.getElementById('album-dropzone');
  const preview = document.getElementById('album-preview');
  if (!input || !zone || !preview) return;
  albumUploadInitialised = true;

  const afficherFichiers = files => {
    const valid = [...files].filter(f => /^image\/(jpeg|png|webp)$/.test(f.type));
    if (!valid.length) return;
    const transfer = new DataTransfer();
    valid.forEach(f => transfer.items.add(f));
    input.files = transfer.files;
    preview.innerHTML = '';
    valid.forEach((file, index) => {
      const reader = new FileReader();
      reader.onload = e => {
        const item = document.createElement('div');
        item.className = 'album-preview-item';
        item.innerHTML = `<img src="${e.target.result}" alt="Aperçu ${index + 1}"><span>${index + 1}</span>`;
        preview.appendChild(item);
      };
      reader.readAsDataURL(file);
    });
    zone.classList.add('has-files');
    zone.querySelector('strong').textContent = `${valid.length} photo${valid.length > 1 ? 's' : ''} sélectionnée${valid.length > 1 ? 's' : ''}`;
    zone.querySelector('span').textContent = 'Cliquez pour modifier la sélection';
  };

  input.addEventListener('change', () => afficherFichiers(input.files));
  ['dragenter','dragover'].forEach(type => zone.addEventListener(type, e => { e.preventDefault(); zone.classList.add('dragging'); }));
  ['dragleave','drop'].forEach(type => zone.addEventListener(type, e => { e.preventDefault(); zone.classList.remove('dragging'); }));
  zone.addEventListener('drop', e => afficherFichiers(e.dataTransfer.files));

  const form = document.getElementById('album-create-form');
  if (form) form.addEventListener('submit', e => {
    if (!input.files.length) { e.preventDefault(); zone.classList.add('upload-error'); }
  });
}

function initialiserRechercheClient() {
  const input = document.getElementById('client-search-input');
  const results = document.getElementById('client-search-results');
  const hidden = document.getElementById('selected-client-id');
  const chip = document.getElementById('selected-client-chip');
  if (!input || !results || !hidden || !chip || input.dataset.ready) return;
  input.dataset.ready = '1';
  let timer;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    hidden.value = '';
    chip.style.display = 'none';
    if (q.length < 2) { results.innerHTML = ''; results.classList.remove('visible'); return; }
    timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/clients/recherche?q=${encodeURIComponent(q)}`);
        const clients = await res.json();
        results.innerHTML = clients.length ? clients.map(c => `<button type="button" class="client-result" data-id="${c.id}" data-name="${escapeHtml(c.nom)}"><span class="client-result-avatar">${c.avatar_url ? `<img src="${c.avatar_url}" alt="">` : escapeHtml(c.nom.charAt(0).toUpperCase())}</span><span><strong>${escapeHtml(c.nom)}</strong><small>${escapeHtml(c.ville || 'Client InstaShoot')}</small></span></button>`).join('') : '<div class="client-search-empty">Aucun client trouvé.</div>';
        results.classList.add('visible');
        results.querySelectorAll('.client-result').forEach(btn => btn.addEventListener('click', () => {
          hidden.value = btn.dataset.id;
          input.value = '';
          results.innerHTML = '';
          results.classList.remove('visible');
          chip.innerHTML = `<span>Client identifié</span><strong>${btn.dataset.name}</strong><button type="button" aria-label="Retirer" onclick="retirerClientSelection()">×</button>`;
          chip.style.display = 'flex';
        }));
      } catch (err) { results.innerHTML = '<div class="client-search-empty">Recherche indisponible.</div>'; results.classList.add('visible'); }
    }, 220);
  });
}
function retirerClientSelection() {
  const hidden = document.getElementById('selected-client-id');
  const chip = document.getElementById('selected-client-chip');
  if (hidden) hidden.value = '';
  if (chip) chip.style.display = 'none';
}
function escapeHtml(value) { const div = document.createElement('div'); div.textContent = value || ''; return div.innerHTML; }

document.addEventListener('DOMContentLoaded', () => {
  initialiserRechercheClient();
  initialiserUploadAlbum();
});

// ============================
// UX moderne : recherche accueil, interactions AJAX, compteurs et dates
// ============================
function ouvrirModalRechercheAccueil() {
  ouvrirModal('modal-recherche-accueil');
  const q = document.getElementById('home-search-q');
  if (q) setTimeout(() => q.focus(), 100);
}

async function soumettreInteractionAjax(form) {
  const response = await fetch(form.action, {
    method: 'POST',
    body: new FormData(form),
    headers: {'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.message || 'Action impossible');
  const button = form.querySelector('.pc-action');
  if (!button) return;
  if ('liked' in data) button.classList.toggle('active', data.liked);
  if ('saved' in data) button.classList.toggle('active', data.saved);
  if ('reposted' in data) button.classList.toggle('active', data.reposted);
  const count = button.querySelector('span');
  if (count && 'count' in data) count.textContent = data.count;
  afficherToast('Action enregistrée');
}

document.addEventListener('submit', async (event) => {
  const form = event.target.closest('form[data-ajax-interaction]');
  if (!form) return;
  event.preventDefault();
  if (form.dataset.busy === '1') return;
  form.dataset.busy = '1';
  try {
    const isComment = form.classList.contains('pc-comment-form');
    if (isComment) {
      const input = form.querySelector('input[name="contenu"]');
      const zone = document.querySelector('.pc-comments');
      const response = await fetch(form.action, {method:'POST', body:new FormData(form), headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}});
      const data = await response.json();
      if (!data.ok) throw new Error(data.message || 'Commentaire impossible');
      if (zone) {
        const empty = zone.querySelector('.empty-comment'); if (empty) empty.remove();
        const p = document.createElement('p'); p.innerHTML = `<strong>${escapeHtml(data.author)}</strong> ${escapeHtml(data.content)}`; zone.appendChild(p);
      }
      if (input) input.value='';
      const counter = document.querySelector('.pc-post-actions .pc-action:nth-child(2) span'); if (counter) counter.textContent=data.count;
      afficherToast('Commentaire publié');
    } else {
      await soumettreInteractionAjax(form);
    }
  } catch (err) { afficherToast(err.message || 'Une erreur est survenue.'); }
  finally { form.dataset.busy='0'; }
});

// ============================
// Double-tap pour liker une photo (geste signature façon Instagram)
// ============================
const derniersTaps = new WeakMap();

function afficherCoeurFlottant(zone) {
  const coeur = document.createElement('div');
  coeur.className = 'pc-doubletap-heart';
  coeur.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20.8 8.7c0 5.5-8.8 10.3-8.8 10.3S3.2 14.2 3.2 8.7A4.7 4.7 0 0 1 12 6.2a4.7 4.7 0 0 1 8.8 2.5Z"/></svg>';
  zone.appendChild(coeur);
  coeur.addEventListener('animationend', () => coeur.remove());
}

async function liker_depuis_doubletap(zone) {
  const url = zone.dataset.likeUrl;
  const postId = zone.dataset.postId;
  if (!url || !postId) return;
  const carte = document.getElementById('publication-' + postId);
  const bouton = carte ? carte.querySelector('.pc-post-actions .pc-action') : null;
  if (bouton && bouton.classList.contains('active')) return; // déjà aimée : juste l'animation, pas de requête

  try {
    const reponse = await fetch(url, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' } });
    const data = await reponse.json();
    if (bouton) {
      if ('liked' in data) bouton.classList.toggle('active', data.liked);
      const compteur = bouton.querySelector('span');
      if (compteur && 'count' in data) compteur.textContent = data.count;
    }
  } catch (e) { /* échec silencieux : l'animation reste visible, ce n'est pas grave */ }
}

document.addEventListener('click', (event) => {
  const zone = event.target.closest('.pc-doubletap-zone');
  if (!zone || event.target.closest('button, .pc-carousel-arrow, .pc-carousel-dot')) return;

  const maintenant = Date.now();
  const dernier = derniersTaps.get(zone) || 0;
  derniersTaps.set(zone, maintenant);

  if (maintenant - dernier < 350) {
    if (!zone.dataset.connecte) {
      ouvrirModalConnexion();
      derniersTaps.set(zone, 0);
      return;
    }
    afficherCoeurFlottant(zone);
    liker_depuis_doubletap(zone);
    derniersTaps.set(zone, 0); // évite un triple-tap qui relancerait un double-tap
  }
});

function initialiserControlesModernes() {
  document.querySelectorAll('.modern-number').forEach(wrap => {
    if (wrap.dataset.ready) return; wrap.dataset.ready='1';
    const input=wrap.querySelector('input[type="number"]');
    wrap.querySelectorAll('button[data-step]').forEach(btn => btn.addEventListener('click',()=>{
      const step=Number(btn.dataset.step||1), min=input.min!==''?Number(input.min):-Infinity, max=input.max!==''?Number(input.max):Infinity;
      let val=Number(input.value||0)+step; val=Math.max(min,Math.min(max,val)); input.value=val; input.dispatchEvent(new Event('input',{bubbles:true}));
    }));
  });
  document.querySelectorAll('input[type="date"]').forEach(input=>input.classList.add('modern-date-input'));
}
document.addEventListener('DOMContentLoaded', initialiserControlesModernes);

// Recherche universelle depuis la messagerie : clients ET photographes.
function initialiserRechercheUtilisateurs(){
  const input=document.getElementById('recherche-utilisateurs');
  const results=document.getElementById('resultats-utilisateurs');
  if(!input||!results||input.dataset.ready)return;
  input.dataset.ready='1';
  let timer;
  input.addEventListener('input',()=>{
    clearTimeout(timer);
    const q=input.value.trim();
    if(q.length<2){ results.innerHTML=''; results.classList.remove('visible'); return; }
    timer=setTimeout(async()=>{
      try{
        const r=await fetch('/api/utilisateurs/recherche?q='+encodeURIComponent(q));
        const users=await r.json();
        results.innerHTML=users.length ? users.map(u=>{
          const avatar=u.avatar_url ? `<img src="${escapeHtml(u.avatar_url)}" alt="">` : escapeHtml((u.nom||'?').charAt(0).toUpperCase());
          return `<a class="public-client-result" href="${escapeHtml(u.url)}"><span class="msg-contact-avatar">${avatar}</span><span><strong>${escapeHtml(u.nom)}</strong><small>${escapeHtml(u.role_label)}${u.ville?' · '+escapeHtml(u.ville):''}</small></span></a>`;
        }).join('') : '<div class="client-search-empty">Aucun profil trouvé.</div>';
        results.classList.add('visible');
      }catch(e){ results.innerHTML='<div class="client-search-empty">Recherche indisponible.</div>'; results.classList.add('visible'); }
    },220);
  });
  document.addEventListener('click',e=>{ if(!e.target.closest('.msg-public-search')) results.classList.remove('visible'); });
}

// Téléphone international : indicatif séparé + numéro libre.
// Le serveur continue de recevoir un seul champ "telephone".
const CODES_PAYS = [
  ["AF","+93","Afghanistan"],["ZA","+27","Afrique du Sud"],["AL","+355","Albanie"],["DZ","+213","Algérie"],
  ["DE","+49","Allemagne"],["AD","+376","Andorre"],["AO","+244","Angola"],["AG","+1","Antigua-et-Barbuda"],
  ["SA","+966","Arabie saoudite"],["AR","+54","Argentine"],["AM","+374","Arménie"],["AU","+61","Australie"],
  ["AT","+43","Autriche"],["AZ","+994","Azerbaïdjan"],["BS","+1","Bahamas"],["BH","+973","Bahreïn"],
  ["BD","+880","Bangladesh"],["BB","+1","Barbade"],["BE","+32","Belgique"],["BZ","+501","Belize"],
  ["BJ","+229","Bénin"],["BT","+975","Bhoutan"],["BY","+375","Biélorussie"],["BO","+591","Bolivie"],
  ["BA","+387","Bosnie-Herzégovine"],["BW","+267","Botswana"],["BR","+55","Brésil"],["BN","+673","Brunei"],
  ["BG","+359","Bulgarie"],["BF","+226","Burkina Faso"],["BI","+257","Burundi"],["KH","+855","Cambodge"],
  ["CM","+237","Cameroun"],["CA","+1","Canada"],["CV","+238","Cap-Vert"],["CF","+236","Centrafrique"],
  ["TD","+235","Tchad"],["CL","+56","Chili"],["CN","+86","Chine"],["CO","+57","Colombie"],
  ["KM","+269","Comores"],["CG","+242","Congo"],["CD","+243","Congo (RDC)"],["CR","+506","Costa Rica"],
  ["CI","+225","Côte d’Ivoire"],["HR","+385","Croatie"],["CU","+53","Cuba"],["CY","+357","Chypre"],
  ["DK","+45","Danemark"],["DJ","+253","Djibouti"],["DM","+1","Dominique"],["EG","+20","Égypte"],
  ["AE","+971","Émirats arabes unis"],["EC","+593","Équateur"],["ER","+291","Érythrée"],["ES","+34","Espagne"],
  ["EE","+372","Estonie"],["SZ","+268","Eswatini"],["ET","+251","Éthiopie"],["FJ","+679","Fidji"],
  ["FI","+358","Finlande"],["FR","+33","France"],["GA","+241","Gabon"],["GM","+220","Gambie"],
  ["GE","+995","Géorgie"],["GH","+233","Ghana"],["GR","+30","Grèce"],["GD","+1","Grenade"],
  ["GT","+502","Guatemala"],["GN","+224","Guinée"],["GW","+245","Guinée-Bissau"],["GQ","+240","Guinée équatoriale"],
  ["GY","+592","Guyana"],["HT","+509","Haïti"],["HN","+504","Honduras"],["HU","+36","Hongrie"],
  ["IN","+91","Inde"],["ID","+62","Indonésie"],["IQ","+964","Irak"],["IE","+353","Irlande"],
  ["IS","+354","Islande"],["IL","+972","Israël"],["IT","+39","Italie"],["JM","+1","Jamaïque"],
  ["JP","+81","Japon"],["JO","+962","Jordanie"],["KZ","+7","Kazakhstan"],["KE","+254","Kenya"],
  ["KG","+996","Kirghizistan"],["KW","+965","Koweït"],["LA","+856","Laos"],["LV","+371","Lettonie"],
  ["LB","+961","Liban"],["LS","+266","Lesotho"],["LR","+231","Liberia"],["LY","+218","Libye"],
  ["LI","+423","Liechtenstein"],["LT","+370","Lituanie"],["LU","+352","Luxembourg"],["MG","+261","Madagascar"],
  ["MW","+265","Malawi"],["MY","+60","Malaisie"],["MV","+960","Maldives"],["ML","+223","Mali"],
  ["MT","+356","Malte"],["MA","+212","Maroc"],["MR","+222","Mauritanie"],["MU","+230","Maurice"],
  ["MX","+52","Mexique"],["MD","+373","Moldavie"],["MC","+377","Monaco"],["MN","+976","Mongolie"],
  ["ME","+382","Monténégro"],["MZ","+258","Mozambique"],["NA","+264","Namibie"],["NP","+977","Népal"],
  ["NL","+31","Pays-Bas"],["NZ","+64","Nouvelle-Zélande"],["NI","+505","Nicaragua"],["NE","+227","Niger"],
  ["NG","+234","Nigeria"],["NO","+47","Norvège"],["OM","+968","Oman"],["PK","+92","Pakistan"],
  ["PA","+507","Panama"],["PG","+675","Papouasie-Nouvelle-Guinée"],["PY","+595","Paraguay"],["PE","+51","Pérou"],
  ["PH","+63","Philippines"],["PL","+48","Pologne"],["PT","+351","Portugal"],["QA","+974","Qatar"],
  ["RO","+40","Roumanie"],["GB","+44","Royaume-Uni"],["RU","+7","Russie"],["RW","+250","Rwanda"],
  ["KN","+1","Saint-Kitts-et-Nevis"],["LC","+1","Sainte-Lucie"],["VC","+1","Saint-Vincent-et-les-Grenadines"],
  ["WS","+685","Samoa"],["SM","+378","Saint-Marin"],["ST","+239","Sao Tomé-et-Principe"],["SN","+221","Sénégal"],
  ["RS","+381","Serbie"],["SC","+248","Seychelles"],["SL","+232","Sierra Leone"],["SG","+65","Singapour"],
  ["SK","+421","Slovaquie"],["SI","+386","Slovénie"],["SO","+252","Somalie"],["SD","+249","Soudan"],
  ["SS","+211","Soudan du Sud"],["LK","+94","Sri Lanka"],["SR","+597","Suriname"],["SE","+46","Suède"],
  ["CH","+41","Suisse"],["SY","+963","Syrie"],["TW","+886","Taïwan"],["TZ","+255","Tanzanie"],
  ["TH","+66","Thaïlande"],["TG","+228","Togo"],["TO","+676","Tonga"],["TT","+1","Trinité-et-Tobago"],
  ["TN","+216","Tunisie"],["TR","+90","Turquie"],["UG","+256","Ouganda"],["UA","+380","Ukraine"],
  ["UY","+598","Uruguay"],["UZ","+998","Ouzbékistan"],["VU","+678","Vanuatu"],["VA","+39","Vatican"],
  ["VE","+58","Venezuela"],["VN","+84","Viêt Nam"],["YE","+967","Yémen"],["ZM","+260","Zambie"],["ZW","+263","Zimbabwe"]
];

function initialiserTelephonesInternationaux(){
  document.querySelectorAll('input[type="tel"].pc-phone').forEach(input=>{
    // Idempotent : le champ peut exister dans la page et dans une modale.
    if(input.dataset.phoneReady==='1') return;
    input.dataset.phoneReady='1';

    let wrap=input.closest('.pc-phone-field');
    if(!wrap){
      wrap=document.createElement('div');
      wrap.className='pc-phone-field';
      input.parentNode.insertBefore(wrap,input);
      wrap.appendChild(input);
    }

    // Retire une éventuelle ancienne interface générée avant une réinitialisation.
    wrap.querySelectorAll('.pc-country-picker,.pc-country-code-native').forEach(el=>el.remove());

    const select=document.createElement('select');
    select.className='pc-country-code pc-country-code-native';
    select.name=input.name+'_code';
    select.setAttribute('aria-label','Indicatif du pays');
    CODES_PAYS.forEach(([iso,code,name])=>{
      const o=document.createElement('option');
      o.value=code; o.textContent=`${code} · ${name}`; o.dataset.iso=iso;
      if(code==='+229') o.selected=true;
      select.appendChild(o);
    });

    const existingPhone=(input.value||'').trim();
    const match=existingPhone.match(/^(\+\d{1,4})(?:[\s.-]|$)/);
    if(match){
      const exact=[...select.options].find(o=>o.value===match[1]);
      if(exact){ select.value=match[1]; input.value=existingPhone.slice(match[0].length).trim(); }
    }

    const picker=document.createElement('div');
    picker.className='pc-country-picker';
    picker.setAttribute('data-phone-picker','');

    const trigger=document.createElement('button');
    trigger.type='button';
    trigger.className='pc-country-trigger';
    trigger.setAttribute('aria-haspopup','listbox');
    trigger.setAttribute('aria-expanded','false');

    const triggerText=document.createElement('span');
    triggerText.className='pc-country-trigger-text';
    trigger.appendChild(triggerText);

    const menu=document.createElement('div');
    menu.className='pc-country-menu';
    menu.setAttribute('role','listbox');

    const search=document.createElement('input');
    search.type='search'; search.className='pc-country-search';
    search.placeholder='Rechercher un pays ou un indicatif…';
    search.setAttribute('aria-label','Rechercher un pays');
    menu.appendChild(search);

    const options=document.createElement('div');
    options.className='pc-country-options';
    menu.appendChild(options);

    function isoToFlag(iso){return [...iso].map(c=>String.fromCodePoint(127397+c.charCodeAt(0))).join('');}
    function updateTrigger(){
      const option=select.options[select.selectedIndex];
      const iso=option?.dataset.iso || 'BJ';
      triggerText.innerHTML=`<span class="pc-country-flag">${isoToFlag(iso)}</span><strong>${option?.value || '+229'}</strong><span class="pc-country-short">${option?.textContent?.split(' · ')[1] || 'Bénin'}</span>`;
      options.querySelectorAll('.pc-country-option').forEach(el=>el.classList.toggle('selected',el.dataset.value===select.value));
    }
    function renderCountries(filter=''){
      const term=filter.trim().toLowerCase(); options.innerHTML='';
      const matches=CODES_PAYS.filter(([iso,code,name])=>!term||iso.toLowerCase().includes(term)||code.includes(term)||name.toLowerCase().includes(term));
      matches.forEach(([iso,code,name])=>{
        const option=document.createElement('button'); option.type='button'; option.className='pc-country-option'; option.setAttribute('role','option'); option.dataset.value=code; option.dataset.iso=iso;
        option.innerHTML=`<span class="pc-country-name"><span class="pc-country-flag">${isoToFlag(iso)}</span><span>${name}</span></span><strong>${code}</strong>`;
        if(select.value===code) option.classList.add('selected');
        option.addEventListener('click',()=>{select.value=code; updateTrigger(); closePicker(); input.focus();});
        options.appendChild(option);
      });
      if(!matches.length){const empty=document.createElement('div'); empty.className='pc-country-empty'; empty.textContent='Aucun pays trouvé'; options.appendChild(empty);}
    }
    function openPicker(){
      document.querySelectorAll('.pc-country-picker.is-open').forEach(el=>{if(el!==picker)el.classList.remove('is-open');});
      picker.classList.add('is-open'); trigger.setAttribute('aria-expanded','true'); search.value=''; renderCountries();
      setTimeout(()=>search.focus(),0);
    }
    function closePicker(){picker.classList.remove('is-open'); trigger.setAttribute('aria-expanded','false');}

    trigger.addEventListener('click',()=>picker.classList.contains('is-open')?closePicker():openPicker());
    select.addEventListener('change',updateTrigger);
    search.addEventListener('input',()=>renderCountries(search.value));
    search.addEventListener('keydown',e=>{if(e.key==='Escape'){closePicker();trigger.focus();}});
    document.addEventListener('click',e=>{if(!picker.contains(e.target))closePicker();});
    document.addEventListener('keydown',e=>{if(e.key==='Escape')closePicker();});

    // Le numéro est un vrai champ indépendant : il ne disparaît jamais derrière le sélecteur.
    input.classList.add('pc-phone-number');
    input.type='tel';
    input.inputMode='tel';
    picker.append(trigger,menu);
    wrap.insertBefore(picker,input);
    wrap.insertBefore(select,input);
    updateTrigger(); renderCountries();

    const form=input.closest('form');
    if(form && !form.dataset.phoneSubmitReady){
      form.dataset.phoneSubmitReady='1';
      form.addEventListener('submit',()=>{
        const code=form.querySelector('select.pc-country-code-native');
        const phone=form.querySelector('input.pc-phone-number');
        if(code&&phone){
          const number=phone.value.trim().replace(/^\+\d+\s*/,'');
          phone.value=number ? `${code.value} ${number}` : '';
        }
      });
    }
  });
}
document.addEventListener('DOMContentLoaded',()=>{
  initialiserRechercheUtilisateurs();
  initialiserControlesNombre();
  initialiserTelephonesInternationaux();
});

// Contrôles de nombre plus élégants sur tous les formulaires.
function initialiserControlesNombre(){
 document.querySelectorAll('input[type="number"]:not(.modernized-number)').forEach(input=>{
   if(input.closest('.modern-number')) return; input.classList.add('modernized-number');
   const wrap=document.createElement('div'); wrap.className='modern-number'; input.parentNode.insertBefore(wrap,input); wrap.appendChild(document.createElement('button')); const minus=wrap.firstChild; minus.type='button'; minus.textContent='−'; minus.dataset.step='-1'; wrap.appendChild(input); const plus=document.createElement('button'); plus.type='button'; plus.textContent='+'; plus.dataset.step='1'; wrap.appendChild(plus);
   [minus,plus].forEach(btn=>btn.addEventListener('click',()=>{let v=Number(input.value||0), step=Number(btn.dataset.step); const min=input.min!==''?Number(input.min):-Infinity,max=input.max!==''?Number(input.max):Infinity; input.value=Math.max(min,Math.min(max,v+step)); input.dispatchEvent(new Event('change',{bubbles:true}));}));
 });
}

document.addEventListener('DOMContentLoaded',()=>{initialiserRechercheClientsInscrits();initialiserControlesNombre();});


// InstaShoot v9 — menus déroulants premium
function initialiserMenusDeroulantsModernes(){
  document.querySelectorAll('select.modern-native-select').forEach(select=>{
    if(select.dataset.customReady==='1') return;
    select.dataset.customReady='1';
    const wrap=document.createElement('div');
    wrap.className='modern-select';
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
    select.classList.add('modern-select-native');
    const trigger=document.createElement('button');
    trigger.type='button'; trigger.className='modern-select-trigger';
    const label=document.createElement('span'); label.className='modern-select-label';
    trigger.append(label); wrap.appendChild(trigger);
    const menu=document.createElement('div'); menu.className='modern-select-menu'; menu.setAttribute('role','listbox'); wrap.appendChild(menu);
    Array.from(select.options).forEach(option=>{
      const item=document.createElement('button'); item.type='button'; item.className='modern-select-option'; item.dataset.value=option.value; item.setAttribute('role','option');
      item.innerHTML='<span>'+escapeHtml(option.textContent)+'</span><b>✓</b>';
      item.addEventListener('click',()=>{
        select.value=option.value; select.dispatchEvent(new Event('change',{bubbles:true}));
        refresh(); close();
      }); menu.appendChild(item);
    });
    function refresh(){
      const selected=select.options[select.selectedIndex]; label.textContent=selected?selected.textContent:'';
      menu.querySelectorAll('.modern-select-option').forEach(i=>i.classList.toggle('selected',i.dataset.value===select.value));
    }
    function close(){wrap.classList.remove('open'); trigger.setAttribute('aria-expanded','false');}
    trigger.setAttribute('aria-expanded','false'); trigger.addEventListener('click',e=>{e.stopPropagation(); const open=wrap.classList.toggle('open'); trigger.setAttribute('aria-expanded',String(open));});
    select.addEventListener('change',refresh); refresh();
    document.addEventListener('click',e=>{if(!wrap.contains(e.target)) close();});
  });
}

function ouvrirModalDeconnexion(){
  const id=document.getElementById('modal-deconnexion-global')?'modal-deconnexion-global':'modal-deconnexion';
  ouvrirModal(id);
}


// Sélecteur de spécialités prestataire : plusieurs choix, sans saisie manuelle.
function initialiserSpecialitesInscription(){
  document.querySelectorAll('[data-specialties-picker]').forEach(root=>{
    if(root.dataset.ready==='1') return;
    root.dataset.ready='1';
    const picker=root.querySelector('.pc-specialties-picker');
    const trigger=root.querySelector('.pc-specialties-trigger');
    const label=root.querySelector('.pc-specialties-label');
    const value=root.querySelector('.pc-specialties-value');
    const options=[...root.querySelectorAll('.pc-specialty-option')];
    if(!picker||!trigger||!label||!value) return;

    function selected(){ return options.filter(o=>o.querySelector('input')?.checked).map(o=>o.querySelector('input').value); }
    function refresh(){
      const values=selected();
      value.value=values.join(', ');
      label.textContent=values.length ? values.join(', ') : 'Choisir vos spécialités';
      label.classList.toggle('has-value', values.length>0);
      options.forEach(o=>o.classList.toggle('selected',!!o.querySelector('input')?.checked));
    }
    function close(){ picker.classList.remove('is-open'); trigger.setAttribute('aria-expanded','false'); }
    function open(){
      document.querySelectorAll('.pc-specialties-picker.is-open').forEach(el=>{if(el!==picker)el.classList.remove('is-open');});
      picker.classList.add('is-open'); trigger.setAttribute('aria-expanded','true');
    }
    trigger.addEventListener('click',e=>{e.stopPropagation(); picker.classList.contains('is-open')?close():open();});
    options.forEach(option=>{
      const checkbox=option.querySelector('input');
      if(!checkbox) return;
      checkbox.addEventListener('change',()=>{
        // Limite stricte à 3 spécialités.
        if(checkbox.checked && selected().length > 3){
          checkbox.checked=false;
          refresh();
          return;
        }
        refresh();
      });
      option.addEventListener('click',e=>{
        e.preventDefault();
        e.stopPropagation();
        const wasChecked=checkbox.checked;
        if(!wasChecked && selected().length >= 3){
          refresh();
          return;
        }
        checkbox.checked=!wasChecked;
        checkbox.dispatchEvent(new Event('change',{bubbles:true}));
      });
    });
    document.addEventListener('click',e=>{if(!picker.contains(e.target))close();});
    document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
    const form=root.closest('form');
    if(form && !form.dataset.specialtiesValidationReady){
      form.dataset.specialtiesValidationReady='1';
      form.addEventListener('submit',e=>{
        refresh();
        if(!value.value.trim()){
          e.preventDefault();
          picker.classList.add('is-invalid');
          open();
        }else{ picker.classList.remove('is-invalid'); }
      });
    }
    refresh();
  });
}

document.addEventListener('DOMContentLoaded',()=>{initialiserMenusDeroulantsModernes();initialiserSpecialitesInscription();});


/* =========================================================
   AFFICHER / MASQUER LE MOT DE PASSE
   Délégation d'événement : fonctionne aussi dans les modales
   ========================================================= */
function togglePasswordVisibility(button) {
  const field = button.closest('.password-field');
  if (!field) return;

  const input = field.querySelector('input[type="password"], input[type="text"]');
  if (!input) return;

  const isVisible = input.type === 'text';
  input.type = isVisible ? 'password' : 'text';

  button.classList.toggle('is-visible', !isVisible);
  button.setAttribute('aria-label', isVisible ? 'Afficher le mot de passe' : 'Masquer le mot de passe');
  button.setAttribute('title', isVisible ? 'Afficher le mot de passe' : 'Masquer le mot de passe');
}

document.addEventListener('click', function(event) {
  const button = event.target.closest('.password-toggle');
  if (!button) return;
  event.preventDefault();
  togglePasswordVisibility(button);
});
