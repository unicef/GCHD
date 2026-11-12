# GCHD Web Application

Interactive dashboard for the Global Child Hazard Database.

## Tech Stack

| Component | Technology |
|---|---|
| Web framework | [Python Dash](https://dash.plotly.com/) |
| Map layer | [dash-leaflet](https://dash-leaflet.onrender.com/) with GEE tile URLs |
| Charts | [Plotly](https://plotly.com/python/) |
| Hazard data | [Google Earth Engine](https://earthengine.google.com/) (Python API) |
| AI query | Google Gemini (natural language → map action) |
| Authentication | OTP via Gmail SMTP |
| Server | Gunicorn + Nginx |

## File Structure

```
web_app/
├── app.py              # Main Dash layout and callbacks
├── gee_core.py         # GEE authentication, tile URL generation, exposure queries
├── ai_core.py          # Gemini AI integration for natural language queries
├── config.py           # Hazard list, topics, colour palettes, admin level config
├── auth.py             # OTP generation, validation, SQLite store, SMTP sender
├── requirements.txt    # Python dependencies
├── nginx-pixel-aid.conf
├── credentials/        # Secret files — see setup below (NEVER committed to git)
└── assets/
    ├── style.css
    └── unicef_*.png
```

## Setup

### 1. Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Credentials

Create the following files in `credentials/` (excluded from git):

| File | Contents |
|---|---|
| `service_account.json` | GEE service account key JSON |
| `gemini_api_key.txt` | Google Gemini API key |
| `flask_secret.txt` | Flask session secret (any random string) |
| `smtp_user.txt` | Gmail address used to send OTP emails |
| `smtp_pass.txt` | Gmail app password for the SMTP account |

### 3. Google Earth Engine

The app authenticates to GEE using the service account key at `credentials/service_account.json`. The service account must have read access to the GEE assets under `projects/unicef-ccri/assets/`.

### 4. Run (development)

```bash
python app.py
```

App runs at http://localhost:8502.

### 5. Deploy (production)

```bash
gunicorn -w 4 -b 127.0.0.1:8502 app:server
```

Configure Nginx using `nginx-pixel-aid.conf` as a template. Update the `server_name` directive to match your domain and update SSL certificate paths.

## Environment Notes

- The app serves OTP-authenticated access; users must authenticate with a registered email before viewing data.
- Gemini AI integration allows natural language queries (e.g., "show flood exposure in Ethiopia") that are translated to map layer actions.
