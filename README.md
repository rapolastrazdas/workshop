# Urza's Workshop

Vietinė MTG kaladžių kūrimo sistema. NI-01: registracija, prisijungimas ir
atsijungimas. Sąsaja – Vue 3 ir TypeScript, serveris – Python ir FastAPI,
duomenų bazė – PostgreSQL. Qdrant ir DI bus pridėti vėlesnėse istorijose.

## Paleidimas su Docker

Reikia veikiančio „Docker Desktop“ su WSL 2. Pirmą kartą reikės interneto
atvaizdams ir priklausomybėms atsisiųsti.

1. Pasirinktinai nukopijuokite `.env.example` į `.env` ir pakeiskite nustatymus.
2. Paleiskite `paleisti.bat` arba repozitorijos aplanke vykdykite:

```powershell
docker compose up --build -d --wait
```

3. Naršyklėje atidarykite **http://localhost:8080**.

Sustabdyti: `sustabdyti.bat` arba `docker compose stop`.
PostgreSQL duomenys lieka vardiniame `postgres_data` tome sustabdžius ar
perkūrus konteinerius. `docker compose down -v` ištrina duomenis.
DB ir API prievadai kompiuterio tinkle neviešinami. Sąsaja pasiekiama tik
šiame kompiuteryje. `APP_PORT` leidžia pakeisti 8080 prievadą.

Naudojimui iš kito įrenginio reikės prieigos prie to paties serverio per
HTTPS. Dabartinis paleidimas skirtas `localhost`.

## Paleidimas be Docker kūrimui

Reikia Python 3.13 ir Node.js 24. SQLite yra vietinio kūrimo ir testavimo
alternatyva. Docker aplinka naudoja PostgreSQL.

Repozitorijos aplanke vieną kartą:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
cd frontend
npm.cmd ci
cd ..
```

Pirmame terminale:

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Antrame terminale:

```powershell
cd frontend
npm.cmd run dev
```

Atidarykite **http://127.0.0.1:5173**. Duomenys lieka `backend/workshop.db`.
Vite persiunčia `/api` į FastAPI; naršyklei tai ta pati kilmė.
Vietinei PostgreSQL prieš migraciją ir serverio paleidimą nustatykite
`DATABASE_URL=postgresql+psycopg://naudotojas:slaptazodis@localhost:5432/workshop`
pagal savo DB nustatymus. `.env` automatiškai skaito Docker Compose;
tiesiogiai paleidžiamam Python kintamuosius nustatykite terminale.

## Patikros

Serverio testai iš `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

TypeScript patikra ir sąsajos surinkimas iš `frontend`:

```powershell
npm.cmd run build
```

Naršyklės testams reikia veikiančių serverio ir sąsajos. Testai sukuria
paskyrų atsitiktiniais adresais, todėl naudokite atskirą kūrimo DB.
Iš `frontend`:

```powershell
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

Galima naudoti įdiegtą Edge: `$env:PLAYWRIGHT_CHANNEL='msedge'`.
Kitam sąsajos adresui: `$env:BASE_URL='http://localhost:8080'`.

## NI-01 apimtis

Formos, atsijungimas, 60 min. sesija, apsaugoti kaladžių adresai ir
„Mano kaladės“ ruošinys. Pagrindiniame puslapyje kol kas yra tik antraštė
ir poraštė. „Šalinti paskyrą“ mygtukas išjungtas iki NI-02.
Kortų paieška ir kaladžių tvarkymas dar neįgyvendinti.

API ir sprendimai: [docs/NI-01.md](docs/NI-01.md).

Paleidimo tvarka remiasi [Docker Compose sveikatos patikromis](https://docs.docker.com/compose/how-tos/startup-order/),
maršrutų apsauga – [Vue Router navigacijos sargais](https://router.vuejs.org/guide/advanced/navigation-guards.html),
slaptažodžių maišos – [FastAPI autentifikacijos gairėmis](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/).
