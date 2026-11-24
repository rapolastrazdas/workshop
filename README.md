# Urza's Workshop

MTG kortų kaladžių kūrimo sistema. Šiuo metu veikia registracija,
prisijungimas, atsijungimas, paskyros ištrynimas ir savo kaladžių sąrašo peržiūra.
Galima kurti kalades, keisti jų pavadinimus ir importuoti papildomus tekstinius kortų sąrašus iš turimo kortų katalogo.
Visas kaladžių redagavimas ir kortų paieška bus pridėti vėliau.

## Paleidimas su Docker

- Git projektui atsisiųsti.
- Paleisto Docker Desktop (Windows sistemoje – su WSL 2).
- Interneto pirmam paleidimui.

Atsisiųskite repozitoriją ir jos aplanke paleiskite `paleisti.bat`
(Windows) arba terminale vykdykite:

```sh
docker compose up --build -d --wait
```

Duomenų bazė ir jos lentelės paruošiamos automatiškai.

Naršyklėje atidarykite **http://localhost:8080**.

Norėdami sustabdyti, paleiskite `sustabdyti.bat` (Windows) arba vykdykite:

```sh
docker compose stop
```

Sustabdžius programą, duomenys išlieka.

## Testai

Testams papildomai reikia Python 3.13 ir Node.js 24.
Toliau pateiktos komandos skirtos Windows PowerShell.

Serverio testai (pradėkite repozitorijos aplanke):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

Šie testai naudoja atskirą laikiną SQLite bazę ir nereikalauja paleistos programos.

Naršyklės testams pirmiausia paleiskite programą su Docker.
Naujame terminale, repozitorijos aplanke:

```powershell
cd frontend
npm.cmd ci
npx.cmd playwright install chromium
$env:BASE_URL='http://localhost:8080'
npm.cmd run test:e2e
```

Testai sukuria testines paskyras veikiančioje duomenų bazėje.
