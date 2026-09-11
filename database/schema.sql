-- ============================================================
-- Schéma de base de données — PhotoConnect
-- À exécuter dans Supabase : Project → SQL Editor → New query
-- ============================================================

-- Table des profils utilisateurs (clients ET photographes)
-- Liée automatiquement au système d'authentification de Supabase
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('client', 'photographe')),
  nom text not null,
  telephone text,
  ville text,
  avatar_url text,
  created_at timestamp with time zone default now()
);

-- Informations spécifiques aux photographes (vitrine pro)
create table photographe_profils (
  id uuid primary key references profiles(id) on delete cascade,
  presentation text,
  specialites text[],           -- ex: {'mariage', 'portrait', 'mode'}
  annees_experience integer,
  tarif_min integer,            -- tarif de départ en FCFA
  reseaux_sociaux text,
  verifie boolean default false
);

-- Photos du portfolio d'un photographe
create table portfolio_photos (
  id uuid primary key default gen_random_uuid(),
  photographe_id uuid references photographe_profils(id) on delete cascade,
  image_url text not null,
  legende text,
  created_at timestamp with time zone default now()
);

-- Demandes de devis / réservations
create table reservations (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references profiles(id) on delete cascade,
  photographe_id uuid references photographe_profils(id) on delete cascade,
  type_prestation text not null,
  date_prestation date,
  budget integer,
  message text,
  statut text default 'en_attente' check (statut in ('en_attente', 'acceptee', 'refusee', 'terminee')),
  created_at timestamp with time zone default now()
);

-- Avis laissés par les clients après une prestation
create table avis (
  id uuid primary key default gen_random_uuid(),
  reservation_id uuid references reservations(id) on delete cascade,
  client_id uuid references profiles(id) on delete cascade,
  photographe_id uuid references photographe_profils(id) on delete cascade,
  note integer check (note between 1 and 5),
  commentaire text,
  created_at timestamp with time zone default now()
);

-- ============================================================
-- Sécurité (Row Level Security) — indispensable sur Supabase
-- ============================================================

alter table profiles enable row level security;
alter table photographe_profils enable row level security;
alter table portfolio_photos enable row level security;
alter table reservations enable row level security;
alter table avis enable row level security;

-- Tout le monde peut voir les profils et portfolios (vitrine publique)
create policy "Profils visibles par tous" on profiles for select using (true);
create policy "Profils photographes visibles par tous" on photographe_profils for select using (true);
create policy "Portfolio visible par tous" on portfolio_photos for select using (true);

-- Un utilisateur ne peut modifier que son propre profil
create policy "Modifier son propre profil" on profiles for update using (auth.uid() = id);
create policy "Modifier son propre profil photographe" on photographe_profils for update using (auth.uid() = id);

-- Un utilisateur peut créer son profil à l'inscription
create policy "Creer son profil" on profiles for insert with check (auth.uid() = id);
create policy "Creer son profil photographe" on photographe_profils for insert with check (auth.uid() = id);

-- Réservations visibles seulement par le client et le photographe concernés
create policy "Voir ses propres reservations" on reservations for select
  using (auth.uid() = client_id or auth.uid() = photographe_id);
create policy "Creer une reservation" on reservations for insert
  with check (auth.uid() = client_id);

-- Avis visibles par tous, mais créés seulement par le client concerné
create policy "Avis visibles par tous" on avis for select using (true);
create policy "Creer un avis" on avis for insert with check (auth.uid() = client_id);
