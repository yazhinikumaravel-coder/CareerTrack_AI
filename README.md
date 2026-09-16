# CareerTrack AI

A Flask + SQLite career planning application with account authentication, personal tasks, progress tracking, an AI schedule planner, PWA support, and browser notifications.

## Structure

```text
CareerTrack_AI/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── career.db
├── templates/
│   ├── login.html
│   ├── register.html
│   └── index.html
└── static/
    ├── css/
    │   └── style.css
    ├── js/
    │   ├── auth.js
    │   └── app.js
    ├── manifest.json
    └── service-worker.js
```

## Local Windows setup

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`.

An OpenAI API key is optional. Without one, the app uses its built-in local schedule generator.

## Public deployment

For a first public release, keep this frontend/backend structure but use a managed PostgreSQL database rather than SQLite when you expect multiple users. Store `SECRET_KEY`, `OPENAI_API_KEY`, and database credentials as hosting-provider environment variables; never commit `.env` or real API keys.

Use a production WSGI server such as Gunicorn on Linux hosting. The Flask development server is for local development only.

## Security notes

- Passwords are hashed with Werkzeug.
- User-specific task and preference queries are scoped by the logged-in user ID.
- API keys belong on the server, not in JavaScript.
- Use HTTPS in production.
- Set a strong random `SECRET_KEY` in production.

## Current database note

This version intentionally uses the requested `career.db` SQLite file for local development. For a public multi-user deployment, migrate the SQL layer to PostgreSQL before launch. The UI and API structure can remain the same.
