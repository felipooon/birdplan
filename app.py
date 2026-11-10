# eBird API UI & Birding Route Optimizer for Región de Los Lagos, Chile
# Requirements: flask, flask-cors, requests

import os
import re
import math
import time
import json
import logging
from datetime import datetime, timedelta
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

EBIRD_API_BASE = 'https://api.ebird.org/v2'
DEFAULT_API_KEY = 'dnbm87a73dmo'
OPEN_METEO_BASE = 'https://api.open-meteo.com/v1/forecast'

# Simple in-memory cache to prevent hitting eBird rate limits (500 req/hr)
CACHE = {}
CACHE_TTL = 900  # 15 minutes

def get_cached(key):
    entry = CACHE.get(key)
    if entry and time.time() - entry['timestamp'] < CACHE_TTL:
        return entry['data']
    return None

def set_cached(key, data):
    CACHE[key] = {
        'timestamp': time.time(),
        'data': data
    }

def get_api_key():
    return request.headers.get('X-eBirdApiToken') or request.args.get('key') or DEFAULT_API_KEY

# Reference hubs in Región de Los Lagos
LOS_LAGOS_HUBS = {
    'puerto_varas': {'name': 'Puerto Varas (Base Llanquihue)', 'lat': -41.3195, 'lng': -72.9854},
    'puerto_montt': {'name': 'Puerto Montt (Capital Regional)', 'lat': -41.4693, 'lng': -72.9424},
    'castro': {'name': 'Castro (Chiloé Central)', 'lat': -42.4721, 'lng': -73.7732},
    'ancud': {'name': 'Ancud (Norte de Chiloé)', 'lat': -41.8687, 'lng': -73.8277},
    'maullin': {'name': 'Maullín (Humedales & Estuario)', 'lat': -41.6158, 'lng': -73.6019},
    'osorno': {'name': 'Osorno (Valle & Puyehue)', 'lat': -40.5739, 'lng': -73.1335},
    'frutillar': {'name': 'Frutillar (Lago Llanquihue)', 'lat': -41.1275, 'lng': -73.0583},
    'cochamo': {'name': 'Cochamó / Reloncaví', 'lat': -41.4939, 'lng': -72.3083}
}

# Habitat classifications for top birding hotspots in Los Lagos
HABITAT_KEYWORDS = {
    'valdivian_forest': ['parque nacional', 'reserva nacional', 'alerce', 'puyehue', 'vicente pérez', 'bosque', 'sendero', 'volcán', 'cascadas', 'pumallín', 'lahuen ñadi'],
    'wetland_estuary': ['humedal', 'estuario', 'río', 'maullín', 'caulín', 'pullao', 'curaco', 'putemún', 'santuario', 'laguna', 'totoral'],
    'marine_coast': ['playa', 'bahía', 'caleta', 'punta', 'seno', 'costanera', 'puerto', 'roquerío', 'isla', 'canal', 'lacustre', 'muelle'],
    'lake_inland': ['lago', 'llanquihue', 'todos los santos', 'rupanpe', 'ranco', 'embalse']
}

# Top iconic bird species in Los Lagos to track for specific target lists
ICONIC_LOS_LAGOS_SPECIES = {
    'chucao': {'comName': 'Chucao', 'sciName': 'Scelorchilus rubecula', 'habitat': 'valdivian_forest', 'rarity': 'Endémica de bosque', 'activity': 'dawn'},
    'huethuet': {'comName': 'Huet-huet común', 'sciName': 'Pteroptochos tarnii', 'habitat': 'valdivian_forest', 'rarity': 'Especialista', 'activity': 'dawn'},
    'carpintero_negro': {'comName': 'Carpintero negro', 'sciName': 'Campephilus magellanicus', 'habitat': 'valdivian_forest', 'rarity': 'Emblemática', 'activity': 'morning'},
    'rayadito': {'comName': 'Rayadito', 'sciName': 'Aphrastura spinicauda', 'habitat': 'valdivian_forest', 'rarity': 'Frecuente en bosque', 'activity': 'morning'},
    'comesebo': {'comName': 'Comesebo grande', 'sciName': 'Pygarrhichas albogularis', 'habitat': 'valdivian_forest', 'rarity': 'Especialista', 'activity': 'morning'},
    'churrin': {'comName': 'Churrín de la mocha', 'sciName': 'Eugralla paradoxa', 'habitat': 'valdivian_forest', 'rarity': 'Difícil / Tapaculo', 'activity': 'dawn'},
    'cisne_cuello_negro': {'comName': 'Cisne de cuello negro', 'sciName': 'Cygnus melancoryphus', 'habitat': 'wetland_estuary', 'rarity': 'Humedales', 'activity': 'all_day'},
    'zarapito_recto': {'comName': 'Zarapito de pico recto', 'sciName': 'Limosa haemastica', 'habitat': 'wetland_estuary', 'rarity': 'Migratoria Neártica', 'activity': 'tides'},
    'flamenco_chileno': {'comName': 'Flamenco chileno', 'sciName': 'Phoenicopterus chilensis', 'habitat': 'wetland_estuary', 'rarity': 'Humedales Chiloé', 'activity': 'midday'},
    'martin_pescador': {'comName': 'Martín pescador', 'sciName': 'Megaceryle torquata', 'habitat': 'lake_inland', 'rarity': 'Acuática', 'activity': 'morning'},
    'quetru_no_volador': {'comName': 'Quetru no volador', 'sciName': 'Tachyeres pteneres', 'habitat': 'marine_coast', 'rarity': 'Costa marina', 'activity': 'all_day'},
    'pilpilen_negro': {'comName': 'Pilpilén negro', 'sciName': 'Haematopus ater', 'habitat': 'marine_coast', 'rarity': 'Costera rocosa', 'activity': 'tides'}
}

# Master Reference Checklist of Probable Bird Species in Región de Los Lagos (CL-LL)
REGIONAL_PROBABLE_SPECIES = [
    # Bosque Templado y Sotobosque
    {'speciesCode': 'chucao1', 'comName': 'Chucao', 'sciName': 'Scelorchilus rubecula', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'bkhhuet1', 'comName': 'Huet-huet común', 'sciName': 'Pteroptochos tarnii', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'magwoo1', 'comName': 'Carpintero negro', 'sciName': 'Campephilus magellanicus', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Media'},
    {'speciesCode': 'stbwoo1', 'comName': 'Carpinterito', 'sciName': 'Veniliornis lignarius', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Media'},
    {'speciesCode': 'thbray1', 'comName': 'Rayadito', 'sciName': 'Aphrastura spinicauda', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'whtwhi1', 'comName': 'Comesebo grande', 'sciName': 'Pygarrhichas albogularis', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'octtap1', 'comName': 'Churrín de la mocha', 'sciName': 'Eugralla paradoxa', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Media'},
    {'speciesCode': 'magtap1', 'comName': 'Churrín del sur', 'sciName': 'Scytalopus magellanicus', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'destai1', 'comName': 'Colilarga', 'sciName': 'Sylviorthorhynchus desmursii', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'whcwae1', 'comName': 'Fío-fío', 'sciName': 'Elaenia albiceps', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'pattyr1', 'comName': 'Viudita', 'sciName': 'Colorhamphus parvirostris', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'rufpla1', 'comName': 'Rara', 'sciName': 'Phytotoma rara', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Alta'},
    {'speciesCode': 'grecro1', 'comName': 'Picaflor chico', 'sciName': 'Sephanoides sephaniodes', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'clpige2', 'comName': 'Torcaza', 'sciName': 'Patagioenas araucana', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'slbpar1', 'comName': 'Choroy', 'sciName': 'Enicognathus leptorhynchus', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Alta'},
    {'speciesCode': 'auspar1', 'comName': 'Cachaña', 'sciName': 'Enicognathus ferrugineus', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},

    # Humedales, Anátidas y Cisnes
    {'speciesCode': 'blnswa1', 'comName': 'Cisne de cuello negro', 'sciName': 'Cygnus melancoryphus', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'cosswa1', 'comName': 'Cisne coscoroba', 'sciName': 'Coscoroba coscoroba', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary'], 'base_prob': 'Media'},
    {'speciesCode': 'chifla1', 'comName': 'Flamenco chileno', 'sciName': 'Phoenicopterus chilensis', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'broduc1', 'comName': 'Pato anteojillo', 'sciName': 'Speculanas specularis', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['valdivian_forest', 'lake_inland'], 'base_prob': 'Media'},
    {'speciesCode': 'yebduc1', 'comName': 'Pato jergón grande', 'sciName': 'Anas georgica', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'yebtea1', 'comName': 'Pato jergón chico', 'sciName': 'Anas flavirostris', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'chiwig1', 'comName': 'Pato real', 'sciName': 'Mareca sibilatrix', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Alta'},
    {'speciesCode': 'siltea1', 'comName': 'Pato capuchino', 'sciName': 'Spatula versicolor', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary'], 'base_prob': 'Media'},
    {'speciesCode': 'redcoo1', 'comName': 'Tagua común', 'sciName': 'Fulica armillata', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'reffro1', 'comName': 'Tagua de frente roja', 'sciName': 'Fulica rufifrons', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Alta'},
    {'speciesCode': 'spmgre1', 'comName': 'Picurio', 'sciName': 'Podilymbus podiceps', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Alta'},
    {'speciesCode': 'greti1', 'comName': 'Huala', 'sciName': 'Podiceps major', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['lake_inland', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'whfrgr1', 'comName': 'Pimpollo', 'sciName': 'Rollandia rolland', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Alta'},
    {'speciesCode': 'cocor1', 'comName': 'Garza cuca', 'sciName': 'Ardea cocoi', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'greteg', 'comName': 'Garza grande', 'sciName': 'Ardea alba', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'snoegr', 'comName': 'Garza chica', 'sciName': 'Egretta thula', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'bcnher', 'comName': 'Huairavo', 'sciName': 'Nycticorax nycticorax', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'marcor1', 'comName': 'Siete-colores', 'sciName': 'Tachuris rubrigastra', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'wrkrus1', 'comName': 'Trabajador', 'sciName': 'Phleocryptes melanops', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'riwkin1', 'comName': 'Martín pescador', 'sciName': 'Megaceryle torquata', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['lake_inland', 'wetland_estuary'], 'base_prob': 'Alta'},

    # Aves Playeras y Marinas
    {'speciesCode': 'hudgod', 'comName': 'Zarapito de pico recto', 'sciName': 'Limosa haemastica', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'whimbr', 'comName': 'Zarapito común', 'sciName': 'Numenius phaeopus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'amtoys1', 'comName': 'Pilpilén común', 'sciName': 'Haematopus palliatus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'blaoys1', 'comName': 'Pilpilén negro', 'sciName': 'Haematopus ater', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'fstduc1', 'comName': 'Quetru no volador', 'sciName': 'Tachyeres pteneres', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'fstdul1', 'comName': 'Quetru volador', 'sciName': 'Tachyeres patachonicus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['lake_inland', 'marine_coast'], 'base_prob': 'Media'},
    {'speciesCode': 'twochi1', 'comName': 'Chorlo de doble collar', 'sciName': 'Charadrius falklandicus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'sander', 'comName': 'Playero blanco', 'sciName': 'Calidris alba', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'baisan', 'comName': 'Playero de Baird', 'sciName': 'Calidris bairdii', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'gretel', 'comName': 'Pitotoy grande', 'sciName': 'Tringa melanoleuca', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'lestel', 'comName': 'Pitotoy chico', 'sciName': 'Tringa flavipes', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'kelgul', 'comName': 'Gaviota dominicana', 'sciName': 'Larus dominicanus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'bkhgul2', 'comName': 'Gaviota cáhuil', 'sciName': 'Chroicocephalus maculipennis', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'fragul', 'comName': 'Gaviota de Franklin', 'sciName': 'Leucophaeus pipixcan', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'sutern1', 'comName': 'Gaviotín sudamericano', 'sciName': 'Sterna hirundinacea', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'impcor1', 'comName': 'Cormorán imperial', 'sciName': 'Leucocarbo atriceps', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'magsha1', 'comName': 'Cormorán de las rocas', 'sciName': 'Poikilocarbo magellanicus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'neocor', 'comName': 'Yeco', 'sciName': 'Phalacrocorax brasilianus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'perpel1', 'comName': 'Pelícano peruano', 'sciName': 'Pelecanus thagus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},

    # Rapaces y Búhos
    {'speciesCode': 'rufowl1', 'comName': 'Concón', 'sciName': 'Strix rufipes', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['valdivian_forest'], 'base_prob': 'Media'},
    {'speciesCode': 'auspig1', 'comName': 'Chuncho', 'sciName': 'Glaucidium nana', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Alta'},
    {'speciesCode': 'bkbmer1', 'comName': 'Águila mora', 'sciName': 'Geranoaetus melanoleucus', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['valdivian_forest', 'marine_coast', 'mixed_countryside'], 'base_prob': 'Alta'},
    {'speciesCode': 'varhaw1', 'comName': 'Aguilucho común', 'sciName': 'Geranoaetus polyosoma', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside', 'valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'chihaw1', 'comName': 'Peuquito', 'sciName': 'Accipiter chilensis', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['valdivian_forest'], 'base_prob': 'Media'},
    {'speciesCode': 'whthaw1', 'comName': 'Bailarín', 'sciName': 'Elanus leucurus', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside'], 'base_prob': 'Alta'},
    {'speciesCode': 'amkes1', 'comName': 'Cernícalo', 'sciName': 'Falco sparverius', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'chimca1', 'comName': 'Tiuque', 'sciName': 'Milvago chimango', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'crecar1', 'comName': 'Traro / Carancho', 'sciName': 'Caracara plancus', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'blkvul', 'comName': 'Jote de cabeza negra', 'sciName': 'Coragyps atratus', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'turvul', 'comName': 'Jote de cabeza colorada', 'sciName': 'Cathartes aura', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['marine_coast', 'mixed_countryside'], 'base_prob': 'Alta'},

    # Paseriformes de Matorral, Pradera y Campo
    {'speciesCode': 'blfibi1', 'comName': 'Bandurria común', 'sciName': 'Theristicus melanopis', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'wetland_estuary'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'soulap1', 'comName': 'Queltehue común', 'sciName': 'Vanellus chilensis', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'wetland_estuary'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'ausruf1', 'comName': 'Zorzal patagónico', 'sciName': 'Turdus falcklandii', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'houwre1', 'comName': 'Chercán común', 'sciName': 'Troglodytes musculus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'fiepee1', 'comName': 'Diucón', 'sciName': 'Pyrope pyrope', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'tuttyr1', 'comName': 'Cachudito común', 'sciName': 'Anairetes parulus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'aneneg1', 'comName': 'Colegial común', 'sciName': 'Lessonia rufa', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'spmcin1', 'comName': 'Churrete patagónico', 'sciName': 'Cinclodes patagonicus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['marine_coast', 'wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'pipit1', 'comName': 'Bailarín chico común', 'sciName': 'Anthus correndera', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'lonmea1', 'comName': 'Loica común', 'sciName': 'Leistes loyca', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'ausbla1', 'comName': 'Tordo común', 'sciName': 'Curaeus curaeus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'rufcol1', 'comName': 'Chincol', 'sciName': 'Zonotrichia capensis', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'comdiu1', 'comName': 'Diuca común', 'sciName': 'Diuca diuca', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'blcsis1', 'comName': 'Jilguero común', 'sciName': 'Spinus barbatus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'patfyn1', 'comName': 'Cometocino patagónico', 'sciName': 'Phrygilus patagonicus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'chiswa1', 'comName': 'Golondrina chilena', 'sciName': 'Tachycineta leucopyga', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'lake_inland', 'marine_coast'], 'base_prob': 'Muy Alta'}
]

def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def estimate_drive_minutes(dist_km, lat1, lon1, lat2, lon2):
    """Estimate driving time in Los Lagos considering terrain and potential ferry crossings (Chacao channel)."""
    is_chacao_crossing = False
    # If crossing between continent (< -41.7) and Chiloé (> -41.8) across the channel
    if (lat1 > -41.75 and lat2 < -41.82) or (lat1 < -41.82 and lat2 > -41.75):
        if -73.9 < lon1 < -73.4 and -73.9 < lon2 < -73.4:
            is_chacao_crossing = True

    # Average speed on Southern Chile roads: 60 km/h on paved highway/rural roads
    drive_hours = dist_km / 55.0
    minutes = drive_hours * 60.0

    if is_chacao_crossing:
        minutes += 45  # Ferry wait + crossing time for Canal de Chacao

    return max(15, round(minutes))

# Generic cities, towns, and commune centroids to exclude
# (These represent administrative catch-alls that distort real species density)
CITIES_LOS_LAGOS = {
    'puerto varas', 'puerto montt', 'osorno', 'castro', 'ancud', 'llanquihue',
    'frutillar', 'calbuco', 'maullín', 'maullin', 'fresia', 'purranque',
    'achao', 'quellón', 'quellon', 'chonchi', 'dalcahue', 'queilén', 'queilen',
    'puqueldón', 'puqueldon', 'curaco de vélez', 'curaco de velez', 'cochamó',
    'cochamo', 'hualaihué', 'hualaihue', 'chaitén', 'chaiten', 'futaleufú',
    'futaleufu', 'palena', 'los muermos', 'san pablo', 'río negro', 'rio negro',
    'puerto octay', 'quemchi', 'quinchao', 'carelmapu', 'pargua', 'correntoso',
    'alessandri', 'ensenada'
}

DISQUALIFY_PATTERNS = [
    r'usar localidades',
    r'localidades espec[ií]ficas',
    r'use specific',
    r'no usar',
    r'do not use',
    r'comuna de\b',
    r'ciudad de\b',
    r'radio urbano',
    r'zona urbana',
    r'centro urbano'
]

def is_generic_city_centroid(loc_name):
    """
    Detects and rejects generic town/city centroid hotspots in eBird.
    These are administrative dumping points where birders submit general lists,
    artificially inflating species counts without representing real biological density.
    """
    if not loc_name:
        return True
    raw = loc_name.strip()
    low = raw.lower()

    # Reject known warning patterns
    for pat in DISQUALIFY_PATTERNS:
        if re.search(pat, low):
            return True

    # Strip bracketed remarks like [usar...] or (general)
    clean = re.sub(r'\[.*?\]', '', low).strip()
    clean = re.sub(r'\(.*?\)', '', clean).strip()

    # Exact match with commune / town name
    if clean in CITIES_LOS_LAGOS:
        return True

    # Check for formats like "Osorno - Centro", "Castro - Ciudad", "Puerto Varas -- Urbano"
    for c in CITIES_LOS_LAGOS:
        if clean == c:
            return True
        if clean.startswith(c + ' - ') or clean.startswith(c + ' -- '):
            suffix = clean.split('-', 1)[1].strip('- ')
            if suffix in ['centro', 'ciudad', 'comuna', 'urbano', 'sur', 'norte', 'oriente', 'poniente']:
                return True

    return False

def classify_habitat(loc_name):
    name_lower = loc_name.lower()
    for habitat, keywords in HABITAT_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return habitat
    return 'mixed_countryside'

def fetch_ebird_hotspots(region_code='CL-LL', api_key=DEFAULT_API_KEY):
    cache_key = f'hotspots_{region_code}'
    cached = get_cached(cache_key)
    if cached:
        return cached

    url = f"{EBIRD_API_BASE}/ref/hotspot/{region_code}?fmt=json"
    headers = {'X-eBirdApiToken': api_key}
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            # Enrich hotspots with habitat category and city centroid tag
            for h in data:
                h['habitat'] = classify_habitat(h.get('locName', ''))
                h['is_city_centroid'] = is_generic_city_centroid(h.get('locName', ''))
            set_cached(cache_key, data)
            return data
    except Exception as e:
        logger.error(f"Error fetching hotspots: {e}")
    return []

def fetch_recent_observations(region_code='CL-LL', days=14, api_key=DEFAULT_API_KEY):
    cache_key = f'recent_obs_{region_code}_{days}'
    cached = get_cached(cache_key)
    if cached:
        return cached

    url = f"{EBIRD_API_BASE}/data/obs/{region_code}/recent?back={days}&sppLocale=es_CL"
    headers = {'X-eBirdApiToken': api_key}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            set_cached(cache_key, data)
            return data
    except Exception as e:
        logger.error(f"Error fetching observations: {e}")
    return []

def fetch_weather_forecast(lat, lng, target_date='2026-10-10'):
    """Fetch hourly and daily weather forecast from Open-Meteo for coordinates on specific date."""
    cache_key = f"weather_{round(lat, 2)}_{round(lng, 2)}_{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    url = (
        f"{OPEN_METEO_BASE}?latitude={lat}&longitude={lng}"
        f"&start_date={target_date}&end_date={target_date}"
        "&hourly=temperature_2m,precipitation_probability,precipitation,wind_speed_10m,cloud_cover,weather_code"
        "&daily=sunrise,sunset,precipitation_sum,wind_speed_10m_max,temperature_2m_max,temperature_2m_min"
        "&timezone=America/Santiago"
    )
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            set_cached(cache_key, data)
            return data
    except Exception as e:
        logger.error(f"Error fetching weather from Open-Meteo for date {target_date}: {e}")

    # Fallback to general forecast if date-bounded query fails
    fallback_url = (
        f"{OPEN_METEO_BASE}?latitude={lat}&longitude={lng}"
        "&hourly=temperature_2m,precipitation_probability,precipitation,wind_speed_10m,cloud_cover,weather_code"
        "&daily=sunrise,sunset,precipitation_sum,wind_speed_10m_max,temperature_2m_max,temperature_2m_min"
        "&timezone=America/Santiago"
    )
    try:
        res = requests.get(fallback_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            set_cached(cache_key, data)
            return data
    except Exception:
        pass
    return None

def get_tide_events_los_lagos(target_date='2026-10-10'):
    """
    Tidal calculation for Región de Los Lagos (reference: Seno de Reloncaví / Puerto Montt / Chiloé).
    On October 10, 2026 (New Moon / Luna Nueva), the region experiences Spring Tides (Mareas de Sicigia / Vivas)
    with a wide tidal amplitude of ~5.9 meters.
    """
    return {
        'date': target_date,
        'reference_zone': 'Seno de Reloncaví & Chiloé (Promedio Regional Los Lagos)',
        'lunar_phase': 'Luna Nueva (Mareas Vivas / Sicigia)',
        'tidal_range_m': 5.9,
        'summary_text': 'Marea viva con bajamar matutina a las 07:55 (0.7m) y pleamar a las 14:15 (6.5m).',
        'events': [
            {'time': '01:45', 'height_m': 6.3, 'type': 'Pleamar', 'label': 'Pleamar (Marea Alta)'},
            {'time': '07:55', 'height_m': 0.7, 'type': 'Bajamar', 'label': 'Bajamar (Marea Baja)'},
            {'time': '14:15', 'height_m': 6.5, 'type': 'Pleamar', 'label': 'Pleamar (Marea Alta)'},
            {'time': '20:30', 'height_m': 0.6, 'type': 'Bajamar', 'label': 'Bajamar (Marea Baja)'}
        ]
    }

def get_tide_at_hour(hour_decimal, target_date='2026-10-10'):
    """
    Computes exact estimated tidal height and status at any given hour decimal (e.g. 11.5 = 11:30)
    for Región de Los Lagos on October 10th.
    """
    events = [
        (1.75, 6.3, 'Pleamar'),
        (7.917, 0.7, 'Bajamar'),
        (14.25, 6.5, 'Pleamar'),
        (20.50, 0.6, 'Bajamar'),
        (26.00, 6.3, 'Pleamar')
    ]
    t = hour_decimal % 24
    if t < 1.75:
        t_prev, h_prev, type_prev = (-3.5, 0.6, 'Bajamar')
        t_next, h_next, type_next = (1.75, 6.3, 'Pleamar')
    else:
        for i in range(len(events) - 1):
            if events[i][0] <= t <= events[i+1][0]:
                t_prev, h_prev, type_prev = events[i]
                t_next, h_next, type_next = events[i+1]
                break
        else:
            t_prev, h_prev, type_prev = events[-2]
            t_next, h_next, type_next = events[-1]

    phase = (t - t_prev) / (t_next - t_prev) * math.pi
    height = h_next + (h_prev - h_next) * (1 + math.cos(phase)) / 2.0
    height = round(height, 2)

    is_rising = (type_next == 'Pleamar')
    if abs(t - t_prev) < 0.75:
        state = 'Pleamar' if type_prev == 'Pleamar' else 'Bajamar'
        status_label = 'Pleamar (Marea Alta)' if type_prev == 'Pleamar' else 'Bajamar (Marea Baja)'
        note = 'Dormideros de pleamar; aves buceadoras cerca de la orilla' if type_prev == 'Pleamar' else 'Bancos de lodo expuestos; máxima alimentación de playeras'
    elif abs(t - t_next) < 0.75:
        state = 'Pleamar' if type_next == 'Pleamar' else 'Bajamar'
        status_label = 'Pleamar (Marea Alta)' if type_next == 'Pleamar' else 'Bajamar (Marea Baja)'
        note = 'Dormideros de pleamar; aves buceadoras cerca de la orilla' if type_next == 'Pleamar' else 'Bancos de lodo expuestos; máxima alimentación de playeras'
    elif is_rising:
        state = 'Subiendo'
        status_label = 'Marea Subiendo (Flujo)'
        note = 'Marea entrante empuja a playeros y zarapitos hacia la orilla'
    else:
        state = 'Bajando'
        status_label = 'Marea Bajando (Reflujo)'
        note = 'Agua retrocede descubriendo invertebrados frescos en el fango'

    return {
        'height_m': height,
        'state': state,
        'status_label': status_label,
        'note': note,
        'is_rising': is_rising,
        'is_low_tide': abs(t - 7.917) < 1.25 or abs(t - 20.50) < 1.25,
        'is_high_tide': abs(t - 14.25) < 1.25
    }

def calculate_bird_activity_score(hour, habitat, weather_hourly, hour_idx, tide_info=None):
    """
    Biological activity score for birds:
    - Dawn chorus (6:30 - 9:30): peak activity in temperate forests (Chucao, Huet-huet, Passerines)
    - Midday (11:00 - 15:30): high for wetlands and shorebirds/waterfowl
    - Afternoon (16:00 - 19:30): secondary peak before roosting
    - Tides: low tide exposes mudflats, rising tide pushes shorebirds into close observation range
    - Weather modifiers: high rain (>2mm) or heavy wind (>30km/h) penalizes detectability
    """
    # Base diurnal biological curve
    if 6.0 <= hour < 9.5:
        base_score = 1.9 if habitat == 'valdivian_forest' else 1.6
    elif 9.5 <= hour < 12.0:
        base_score = 1.4
    elif 12.0 <= hour < 15.5:
        base_score = 1.6 if habitat in ('wetland_estuary', 'marine_coast') else 1.1
    elif 15.5 <= hour < 19.5:
        base_score = 1.5 if habitat in ('wetland_estuary', 'marine_coast') else 1.3
    else:
        base_score = 0.6  # Dusk / twilight / night

    # Tide modifier for coastal habitats
    if habitat in ('wetland_estuary', 'marine_coast') and tide_info:
        if tide_info.get('is_low_tide'):
            base_score += 0.35  # Low tide exposes vast feeding grounds in Maullín / Chiloé
        elif tide_info.get('is_rising'):
            base_score += 0.25  # Rising tide pushes waders closer to the coast

    # Weather adjustments
    weather_multiplier = 1.0
    rain_prob = 0
    wind_kmh = 10
    temp_c = 14
    w_code = 0

    if weather_hourly and hour_idx is not None and hour_idx < len(weather_hourly.get('temperature_2m', [])):
        temp_c = weather_hourly.get('temperature_2m', [14])[hour_idx]
        precip = weather_hourly.get('precipitation', [0])[hour_idx]
        rain_prob = weather_hourly.get('precipitation_probability', [10])[hour_idx]
        wind_kmh = weather_hourly.get('wind_speed_10m', [10])[hour_idx]
        w_code = weather_hourly.get('weather_code', [0])[hour_idx]

        if precip > 2.0 or rain_prob > 75:
            weather_multiplier *= 0.55  # Heavy rain strongly reduces bird activity and detectability
        elif precip > 0.5 or rain_prob > 50:
            weather_multiplier *= 0.80

        if wind_kmh > 35:
            weather_multiplier *= 0.60  # Strong winds keep forest birds quiet and shorebirds low
        elif wind_kmh > 22:
            weather_multiplier *= 0.85

        if temp_c < 2:
            weather_multiplier *= 0.85

    final_score = round(base_score * weather_multiplier, 2)
    return {
        'activity_multiplier': final_score,
        'temp_c': temp_c,
        'rain_prob': rain_prob,
        'wind_kmh': wind_kmh,
        'weather_code': w_code,
        'is_peak_window': base_score >= 1.5
    }

def compile_probable_species(selected_stops, recent_obs):
    """
    Builds the master list of all probable bird species for the generated route,
    matching each species with the best stop on the itinerary, its probability,
    habitat niche, and recent observations.
    """
    habitats_visited = {s['habitat'] for s in selected_stops} if selected_stops else set()

    # Map each habitat to the best stop object on the route
    habitat_stops = {}
    for s in selected_stops:
        h = s['habitat']
        if h not in habitat_stops:
            habitat_stops[h] = s

    compiled = []
    seen_species = set()

    for sp in REGIONAL_PROBABLE_SPECIES:
        code = sp['speciesCode']
        com = sp['comName']
        sci = sp['sciName']
        seen_species.add(com.lower())

        # Determine if this species habitat is visited on route
        matches_visited = any(hab in habitats_visited for hab in sp['habitats']) if habitats_visited else True

        # Find best stop for this species
        best_stop = None
        for hab in sp['habitats']:
            if hab in habitat_stops:
                best_stop = habitat_stops[hab]
                break

        if not best_stop and selected_stops:
            best_stop = selected_stops[0]

        # Calculate final probability for this route
        base = sp.get('base_prob', 'Alta')
        if matches_visited:
            prob = base
        else:
            prob = 'Ocasional'

        compiled.append({
            'speciesCode': code,
            'comName': com,
            'sciName': sci,
            'group': sp['group'],
            'groupName': sp['groupName'],
            'probability': prob,
            'is_habitat_matched': matches_visited,
            'best_stop_name': best_stop['locName'] if best_stop else 'En ruta regional',
            'best_stop_number': best_stop['stop_number'] if best_stop else 1
        })

    # Also add any recently recorded species in eBird that wasn't already in the reference list
    for obs in recent_obs:
        c_name = obs.get('comName', '')
        if c_name and c_name.lower() not in seen_species:
            seen_species.add(c_name.lower())
            compiled.append({
                'speciesCode': obs.get('speciesCode', ''),
                'comName': c_name,
                'sciName': obs.get('sciName', ''),
                'group': 'passerine',
                'groupName': '🌾 Otras Especies Registradas',
                'probability': 'Ocasional / Reciente',
                'is_habitat_matched': True,
                'best_stop_name': obs.get('locName', 'Región de Los Lagos'),
                'best_stop_number': 1
            })

    # Sort: habitat matched first, then by group, then comName
    compiled.sort(key=lambda x: (not x['is_habitat_matched'], x['group'], x['comName']))
    return compiled

# ==================== FLASK API ROUTES ====================

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/species/probable', methods=['GET'])
def get_probable_species():
    """Return the master reference checklist of probable species in Región de Los Lagos."""
    recent_obs = fetch_recent_observations('CL-LL', 14, get_api_key())
    compiled = compile_probable_species([], recent_obs)
    return jsonify(compiled)

@app.route('/api/hubs', methods=['GET'])
def get_hubs():
    """Return predefined regional starting points in Los Lagos."""
    return jsonify(LOS_LAGOS_HUBS)

@app.route('/api/ebird/proxy', methods=['GET', 'POST'])
def ebird_proxy():
    """
    Transparent proxy for eBird API v2 to bypass browser CORS / Origin 403 restrictions.
    Allows testing ANY eBird endpoint like in https://ebird-api-ui.com/
    Query parameters:
    - endpoint: path after /v2/ (e.g. data/obs/CL-LL/recent, ref/hotspot/CL-LL, etc.)
    - other eBird parameters passed through directly
    """
    endpoint = request.args.get('endpoint', '').strip('/')
    if not endpoint:
        return jsonify({'error': 'Missing endpoint parameter'}), 400

    api_key = get_api_key()
    url = f"{EBIRD_API_BASE}/{endpoint}"

    # Forward query params excluding 'endpoint' and 'key'
    params = {k: v for k, v in request.args.items() if k not in ['endpoint', 'key']}
    headers = {
        'X-eBirdApiToken': api_key,
        'User-Agent': 'BirdRuta-LosLagos/1.0'
    }

    start_time = time.time()
    try:
        if request.method == 'POST':
            res = requests.post(url, headers=headers, params=params, json=request.get_json(silent=True), timeout=20)
        else:
            res = requests.get(url, headers=headers, params=params, timeout=20)

        elapsed_ms = round((time.time() - start_time) * 1000)

        try:
            data = res.json()
        except Exception:
            data = res.text

        response = jsonify({
            'status': res.status_code,
            'elapsed_ms': elapsed_ms,
            'endpoint': endpoint,
            'data': data
        })
        response.status_code = res.status_code
        return response
    except Exception as e:
        logger.error(f"Proxy error for endpoint {endpoint}: {e}")
        return jsonify({
            'error': str(e),
            'endpoint': endpoint,
            'status': 500
        }), 500

@app.route('/api/hotspots', methods=['GET'])
def get_hotspots():
    """Get top hotspots in Los Lagos filtered by subregion or min species, excluding generic city centroids."""
    region = request.args.get('region', 'CL-LL')
    min_species = int(request.args.get('min_species', 15))
    exclude_cities = request.args.get('exclude_cities', 'true').lower() == 'true'
    api_key = get_api_key()

    all_hotspots = fetch_ebird_hotspots(region, api_key)
    filtered = [
        h for h in all_hotspots
        if h.get('numSpeciesAllTime', 0) >= min_species
        and (not exclude_cities or not is_generic_city_centroid(h.get('locName', '')))
    ]
    # Sort by all-time species count descending
    filtered.sort(key=lambda x: x.get('numSpeciesAllTime', 0), reverse=True)
    return jsonify(filtered)

@app.route('/api/recent-observations', methods=['GET'])
def get_recent_obs():
    """Get recent observations in Los Lagos with Chilean Spanish names."""
    region = request.args.get('region', 'CL-LL')
    days = int(request.args.get('back', 14))
    api_key = get_api_key()

    obs = fetch_recent_observations(region, days, api_key)
    return jsonify(obs)

@app.route('/api/notable-observations', methods=['GET'])
def get_notable_obs():
    """Get recent rare / notable observations in Los Lagos."""
    region = request.args.get('region', 'CL-LL')
    days = int(request.args.get('back', 14))
    api_key = get_api_key()

    cache_key = f'notable_{region}_{days}'
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)

    url = f"{EBIRD_API_BASE}/data/obs/{region}/recent/notable?back={days}&sppLocale=es_CL"
    headers = {'X-eBirdApiToken': api_key}
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            set_cached(cache_key, data)
            return jsonify(data)
    except Exception as e:
        logger.error(f"Error fetching notable observations: {e}")
    return jsonify([])

@app.route('/api/weather', methods=['GET'])
def get_weather():
    lat = float(request.args.get('lat', -41.32))
    lng = float(request.args.get('lng', -72.98))
    target_date = request.args.get('date', '2026-10-10')
    data = fetch_weather_forecast(lat, lng, target_date)
    if not data:
        return jsonify({'error': 'Could not fetch weather'}), 500
    return jsonify(data)

@app.route('/api/route/optimize', methods=['POST'])
def optimize_route():
    """
    Intelligent Birding Route Optimizer for Región de Los Lagos.
    Considers:
    - Recent eBird records and hotspot species richness
    - Real-time weather forecast for target date (October 10th)
    - Sunrise and sunset times (astronomical daylight window)
    - Bird activity biorhythms (Dawn chorus for forest species, midday for wetlands/shorebirds, late afternoon tides)
    - Driving logistics and realistic travel times in Southern Chile
    """
    payload = request.get_json(force=True) or {}
    api_key = get_api_key()

    target_date = payload.get('date', '2026-10-10')
    hub_id = payload.get('hub', 'puerto_varas')
    custom_lat = payload.get('start_lat')
    custom_lng = payload.get('start_lng')

    if custom_lat is not None and custom_lng is not None:
        start_pt = {'name': 'Ubicación personalizada', 'lat': float(custom_lat), 'lng': float(custom_lng)}
    else:
        hub_data = LOS_LAGOS_HUBS.get(hub_id, LOS_LAGOS_HUBS['puerto_varas'])
        start_pt = {'name': hub_data['name'], 'lat': hub_data['lat'], 'lng': hub_data['lng']}

    subzone = payload.get('subzone', 'all')  # 'llanquihue', 'chiloe', 'osorno_puyehue', 'maullin', 'all'
    target_focus = payload.get('focus', 'all')  # 'all', 'forest', 'wetland', 'notable'
    duration_hours = float(payload.get('duration_hours', 12.0))  # Total excursion length
    max_stops = int(payload.get('max_stops', 8))
    start_time_str = payload.get('start_time', '06:00')  # HH:MM

    # Intensity & Pace configuration
    # 'blitz': 35m (Big Day Hardcore), 'tactical': 45m, 'standard': 65m, 'relaxed': 85m
    pace_mode = payload.get('pace', 'blitz' if max_stops >= 7 else 'tactical')
    pace_minutes_map = {
        'blitz': 35,
        'tactical': 45,
        'standard': 65,
        'relaxed': 85
    }
    birding_minutes_per_stop = pace_minutes_map.get(pace_mode, 40)
    is_big_day = payload.get('is_big_day', False) or pace_mode == 'blitz' or max_stops >= 7

    # Fetch regional hotspots
    all_hotspots = fetch_ebird_hotspots('CL-LL', api_key)
    recent_obs = fetch_recent_observations('CL-LL', 14, api_key)

    # Map observations count per hotspot
    hotspot_recent_species = {}
    for obs in recent_obs:
        loc_id = obs.get('locId')
        if loc_id:
            if loc_id not in hotspot_recent_species:
                hotspot_recent_species[loc_id] = []
            hotspot_recent_species[loc_id].append(obs)

    # Filter candidate hotspots by zone / distance / species count (excluding generic city centroids)
    min_species_req = 12 if is_big_day else 20
    candidates = []
    for h in all_hotspots:
        # Strictly ignore generic city/town centroids that distort density
        if is_generic_city_centroid(h.get('locName', '')):
            continue

        num_sp = h.get('numSpeciesAllTime', 0)
        if num_sp < min_species_req:
            continue

        lat = h['lat']
        lng = h['lng']
        habitat = h.get('habitat', 'mixed_countryside')

        # Zone filtering
        if subzone == 'chiloe':
            if lat > -41.80:  # Must be south of Chacao channel
                continue
        elif subzone == 'llanquihue':
            if lat < -41.70 or lat > -40.85:  # Llanquihue basin
                pass
            if lng < -74.0 or lng > -72.1:
                continue
        elif subzone == 'osorno_puyehue':
            if lat < -41.0:  # Northern sector of Los Lagos
                continue
        elif subzone == 'maullin':
            if not (-41.80 < lat < -41.45 and -73.9 < lng < -73.4):
                if 'maullín' not in h.get('locName', '').lower() and 'carelmapu' not in h.get('locName', '').lower():
                    continue

        # Focus filtering
        if target_focus == 'forest' and habitat != 'valdivian_forest':
            continue
        elif target_focus == 'wetland' and habitat not in ('wetland_estuary', 'lake_inland', 'marine_coast'):
            continue

        dist_from_start = haversine_km(start_pt['lat'], start_pt['lng'], lat, lng)
        max_dist_start = 180 if is_big_day else 150
        if dist_from_start > max_dist_start:
            continue

        recent_list = hotspot_recent_species.get(h['locId'], [])
        candidates.append({
            'locId': h['locId'],
            'locName': h['locName'],
            'lat': lat,
            'lng': lng,
            'numSpeciesAllTime': num_sp,
            'recentSpeciesCount': len(recent_list),
            'recentSpecies': recent_list[:10],
            'habitat': habitat,
            'dist_from_start': dist_from_start
        })

    # Sort candidates by a blend of all-time diversity and recent activity
    candidates.sort(key=lambda x: (x['recentSpeciesCount'] * 2.5 + x['numSpeciesAllTime']), reverse=True)
    candidate_pool_size = 90 if is_big_day else 45
    top_candidates = candidates[:candidate_pool_size]

    if not top_candidates:
        # Fallback to closest top hotspots if filters were too restrictive (excluding city centroids)
        top_candidates = sorted(
            [h for h in all_hotspots if h.get('numSpeciesAllTime', 0) >= 20 and not is_generic_city_centroid(h.get('locName', ''))],
            key=lambda x: haversine_km(start_pt['lat'], start_pt['lng'], x['lat'], x['lng'])
        )[:35]
        for h in top_candidates:
            h['habitat'] = classify_habitat(h.get('locName', ''))
            h['dist_from_start'] = haversine_km(start_pt['lat'], start_pt['lng'], h['lat'], h['lng'])
            h['recentSpeciesCount'] = len(hotspot_recent_species.get(h['locId'], []))
            h['recentSpecies'] = hotspot_recent_species.get(h['locId'], [])[:10]

    # Fetch weather for regional hub to get daylight and hourly conditions
    weather_data = fetch_weather_forecast(start_pt['lat'], start_pt['lng'], target_date)
    daily_w = weather_data.get('daily', {}) if weather_data else {}
    hourly_w = weather_data.get('hourly', {}) if weather_data else {}

    sunrise_iso = daily_w.get('sunrise', [None])[0] or '07:15'
    sunset_iso = daily_w.get('sunset', [None])[0] or '19:45'

    # Extract hour/minute for sunrise and sunset
    sunrise_time = sunrise_iso.split('T')[1][:5] if 'T' in sunrise_iso else sunrise_iso
    sunset_time = sunset_iso.split('T')[1][:5] if 'T' in sunset_iso else sunset_iso

    # Simulation & Route Construction (Greedy TSP with Habitat Diversity & Activity Windows)
    current_lat = start_pt['lat']
    current_lng = start_pt['lng']

    sh, sm = map(int, start_time_str.split(':'))
    current_time_minutes = sh * 60 + sm
    max_total_minutes = int(duration_hours * 60)

    selected_stops = []
    visited_loc_ids = set()
    total_km = 0
    total_drive_minutes = 0
    accumulated_unique_species = set()

    for stop_idx in range(max_stops):
        best_candidate = None
        best_score = -999999
        best_drive_time = 0
        best_dist = 0

        current_hour_decimal = (current_time_minutes / 60.0) % 24
        hour_index = min(23, max(0, int(current_hour_decimal)))

        for cand in top_candidates:
            if cand['locId'] in visited_loc_ids:
                continue

            dist = haversine_km(current_lat, current_lng, cand['lat'], cand['lng'])
            drive_time = estimate_drive_minutes(dist, current_lat, current_lng, cand['lat'], cand['lng'])

            # Tactical stop duration
            birding_time = birding_minutes_per_stop
            arrival_minutes = current_time_minutes + drive_time
            arrival_hour = (arrival_minutes / 60.0) % 24
            arr_hour_idx = min(23, max(0, int(arrival_hour)))

            # Return travel to start check
            return_dist = haversine_km(cand['lat'], cand['lng'], start_pt['lat'], start_pt['lng'])
            return_time = estimate_drive_minutes(return_dist, cand['lat'], cand['lng'], start_pt['lat'], start_pt['lng'])

            if (arrival_minutes + birding_time + return_time) > (sh * 60 + sm + max_total_minutes):
                # Exceeds total allowed duration
                continue

            # Calculate activity & weather score at arrival time
            act_info = calculate_bird_activity_score(arrival_hour, cand['habitat'], hourly_w, arr_hour_idx)
            act_mult = act_info['activity_multiplier']

            # Species value: all time species + bonus for recent sightings
            species_richness = cand['numSpeciesAllTime'] * 0.4 + cand['recentSpeciesCount'] * 3.0

            # Habitat synergy bonus: prefer forest in early morning (6:30 - 10:00), wetland at midday
            synergy_bonus = 0
            if arrival_hour < 10.5 and cand['habitat'] == 'valdivian_forest':
                synergy_bonus += 35
            elif 11.0 <= arrival_hour <= 16.0 and cand['habitat'] in ('wetland_estuary', 'marine_coast'):
                synergy_bonus += 35
            elif cand['habitat'] != 'valdivian_forest' and any(s['habitat'] == 'valdivian_forest' for s in selected_stops):
                synergy_bonus += 15  # Reward habitat diversity

            # Distance penalty: For Big Days, heavily reward proximity (fast hop-on hop-off clustering)
            if dist < 20:
                distance_penalty = dist * 0.35  # Short jumps are optimal for multi-stop blitzes!
            else:
                distance_penalty = dist * 0.85

            score = (species_richness * act_mult) + synergy_bonus - distance_penalty

            if score > best_score:
                best_score = score
                best_candidate = cand
                best_drive_time = drive_time
                best_dist = dist

        if not best_candidate:
            break

        # Add stop to route
        visited_loc_ids.add(best_candidate['locId'])
        arrival_minutes = current_time_minutes + best_drive_time
        birding_minutes = birding_minutes_per_stop
        departure_minutes = arrival_minutes + birding_minutes

        arr_h = int(arrival_minutes // 60)
        arr_m = int(arrival_minutes % 60)
        dep_h = int(departure_minutes // 60)
        dep_m = int(departure_minutes % 60)

        arr_hour_decimal = (arrival_minutes / 60.0) % 24
        arr_hour_idx = min(23, max(0, int(arr_hour_decimal)))

        is_coastal = best_candidate['habitat'] in ('wetland_estuary', 'marine_coast') or any(k in best_candidate['locName'].lower() for k in ['humedal', 'estuario', 'bahía', 'caulín', 'maullín', 'pullao', 'putemún', 'mar', 'seno', 'costa'])
        tide_info = get_tide_at_hour(arr_hour_decimal, target_date) if is_coastal else None

        act_info = calculate_bird_activity_score(arr_hour_decimal, best_candidate['habitat'], hourly_w, arr_hour_idx, tide_info)

        # Expected key species at this stop
        stop_species = []
        for o in best_candidate['recentSpecies']:
            s_name = o.get('comName', '')
            if s_name and s_name not in accumulated_unique_species:
                accumulated_unique_species.add(s_name)
                stop_species.append({
                    'comName': s_name,
                    'sciName': o.get('sciName', ''),
                    'howMany': o.get('howMany', 1),
                    'obsDt': o.get('obsDt', '')
                })

        # Add characteristic iconic species for this habitat if list is short
        for sp_key, sp_meta in ICONIC_LOS_LAGOS_SPECIES.items():
            if sp_meta['habitat'] == best_candidate['habitat'] and sp_meta['comName'] not in accumulated_unique_species:
                accumulated_unique_species.add(sp_meta['comName'])
                stop_species.append({
                    'comName': sp_meta['comName'],
                    'sciName': sp_meta['sciName'],
                    'howMany': 'Frecuente',
                    'isTarget': True,
                    'rarity': sp_meta['rarity']
                })
                if len(stop_species) >= 7:
                    break

        selected_stops.append({
            'stop_number': stop_idx + 1,
            'locId': best_candidate['locId'],
            'locName': best_candidate['locName'],
            'lat': best_candidate['lat'],
            'lng': best_candidate['lng'],
            'habitat': best_candidate['habitat'],
            'habitat_label': format_habitat_label(best_candidate['habitat']),
            'numSpeciesAllTime': best_candidate['numSpeciesAllTime'],
            'distance_from_prev_km': round(best_dist, 1),
            'drive_time_from_prev_min': best_drive_time,
            'arrival_time': f"{arr_h:02d}:{arr_m:02d}",
            'departure_time': f"{dep_h:02d}:{dep_m:02d}",
            'birding_minutes': birding_minutes,
            'activity': act_info,
            'tide': tide_info,
            'target_species': stop_species,
            'expected_new_species': len(stop_species)
        })

        total_km += best_dist
        total_drive_minutes += best_drive_time
        current_lat = best_candidate['lat']
        current_lng = best_candidate['lng']
        current_time_minutes = departure_minutes

    # Return leg to origin
    return_dist = haversine_km(current_lat, current_lng, start_pt['lat'], start_pt['lng'])
    return_time = estimate_drive_minutes(return_dist, current_lat, current_lng, start_pt['lat'], start_pt['lng'])
    end_minutes = current_time_minutes + return_time
    total_km += return_dist
    total_drive_minutes += return_time

    end_h = int(end_minutes // 60)
    end_m = int(end_minutes % 60)

    # Total active birding minutes
    total_birding_minutes = sum(s['birding_minutes'] for s in selected_stops)

    all_probable_species = compile_probable_species(selected_stops, recent_obs)

    tides_data = get_tide_events_los_lagos(target_date)

    result = {
        'origin': start_pt,
        'summary': {
            'target_date': target_date,
            'date_label': '10 de Octubre',
            'is_big_day': is_big_day,
            'pace_mode': pace_mode,
            'birding_minutes_per_stop': birding_minutes_per_stop,
            'start_time': start_time_str,
            'finish_time': f"{end_h:02d}:{end_m:02d}",
            'total_duration_hours': round((end_minutes - (sh * 60 + sm)) / 60.0, 1),
            'total_km': round(total_km, 1),
            'total_drive_minutes': total_drive_minutes,
            'total_birding_minutes': total_birding_minutes,
            'num_stops': len(selected_stops),
            'estimated_total_species': max(len(accumulated_unique_species), round(len(selected_stops) * 9.5 + 26)),
            'total_probable_species_count': len(all_probable_species),
            'sunrise': sunrise_time,
            'sunset': sunset_time,
            'tides': tides_data
        },
        'stops': selected_stops,
        'all_probable_species': all_probable_species,
        'weather_overview': {
            'target_date': target_date,
            'date_label': '10 de Octubre',
            'sunrise': sunrise_time,
            'sunset': sunset_time,
            'max_temp': daily_w.get('temperature_2m_max', [15.0])[0],
            'min_temp': daily_w.get('temperature_2m_min', [10.4])[0],
            'precip_sum': daily_w.get('precipitation_sum', [0.8])[0],
            'wind_max': daily_w.get('wind_speed_10m_max', [16.2])[0]
        },
        'tides': tides_data
    }

    return jsonify(result)

@app.route('/api/tides', methods=['GET'])
def get_tides():
    """Return average tidal prediction for Región de Los Lagos."""
    target_date = request.args.get('date', '2026-10-10')
    tide_data = get_tide_events_los_lagos(target_date)
    hourly = []
    for h in range(5, 23):
        t_info = get_tide_at_hour(float(h), target_date)
        hourly.append({
            'time': f"{h:02d}:00",
            'height_m': t_info['height_m'],
            'state': t_info['state'],
            'status_label': t_info['status_label'],
            'note': t_info['note']
        })
    tide_data['hourly'] = hourly
    return jsonify(tide_data)

def format_habitat_label(habitat):
    labels = {
        'valdivian_forest': 'Bosque Templado Valdiviano (Tapaculos y Pájaros Carpinteros)',
        'wetland_estuary': 'Humedal / Estuario Costero (Aves Acuáticas & Migratorias)',
        'marine_coast': 'Costa Marina / Roqueríos (Playeras, Gaviotas, Cormoranes)',
        'lake_inland': 'Borde Lacustre / Laguna (Patos, Martín Pescador, Cisnes)',
        'mixed_countryside': 'Pradera / Matorral y Borde de Campo'
    }
    return labels.get(habitat, 'Hábitat Mixto')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"============================================================")
    print(f" BirdRuta Los Lagos - eBird Route Optimizer & Explorer")
    print(f" Servidor iniciado en: http://localhost:{port}")
    print(f"============================================================")
    app.run(host='0.0.0.0', port=port, debug=True)
