# Site Config Generator

Streamlit app to generate `host_vars` configuration files for new Pyronear sites.

## Usage

```bash
uv run --with streamlit streamlit run site_config/app.py
```

Then open http://localhost:8501 in your browser.

## Features

- Set site name and number of cameras
- Choose camera type (PTZ or static)
- Auto-generated IPs (`192.168.1.11`, `.12`, ...), names, and azimuths
- Configurable adapter (with custom option), camera ID, number of poses, anonymizer
- Download the generated `vars` file or raw JSON
