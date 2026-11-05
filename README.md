# Network — CS50W Project 4

[![CI](https://github.com/dianr6boy1386/network/actions/workflows/ci.yml/badge.svg)](https://github.com/dianr6boy1386/network/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Django](https://img.shields.io/badge/django-5.2%20%7C%206.x-092e20)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A small Twitter-style social network built with **Django** and **JavaScript**.
Users can publish posts, follow each other, like posts and edit their own posts in place, all
without full page reloads.

Built as the fifth project of [CS50's Web Programming with Python and JavaScript](https://cs50.harvard.edu/web/),
then hardened with input validation, authorization checks, an automated test suite and CI.


## Video demo

[Watch the project demo on YouTube](https://youtu.be/)


## Features

- **Accounts**: register, log in and log out (with safe `?next=` redirects).
- **Posts**: write text posts (up to 500 characters) from the home page.
- **All Posts**: a global feed, newest first, 10 posts per page with Previous / Next navigation.
- **Profiles**: follower / following counts, the user's posts in reverse-chronological order,
  and a Follow / Unfollow button (you cannot follow yourself).
- **Following feed**: posts only from people you follow (login required).
- **Inline editing**: edit your own posts with a textarea and Save / Cancel, using JavaScript `fetch`.
- **Likes**: like and unlike any post; the count updates instantly without a reload.
- **Admin**: Django admin with users, follows and posts registered.

## Tech stack

| Layer     | Technology                                                  |
|-----------|-------------------------------------------------------------|
| Backend   | Python 3.12+, Django 5.2 LTS / 6.x                          |
| Database  | SQLite (default, swappable through Django's `DATABASES`)    |
| Front end | Django templates, Bootstrap 4, vanilla JavaScript (`fetch`) |
| Testing   | Django's test framework, GitHub Actions CI                  |

## Getting started

```bash
git clone https://github.com/dianr6boy1386/Network.git
cd Network

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

### Optional: demo data

```bash
python manage.py seed_demo
```

Creates the users `alice`, `bob` and `carol` (password `demo-pass-12345`) with posts, follows
and likes so you can explore the app right away. The command is safe to run more than once.
For development only.

### Admin site

```bash
python manage.py createsuperuser
```

Then visit <http://127.0.0.1:8000/admin/>.

## Running the tests

```bash
python manage.py test
```

The suite covers models, authentication, pagination, the following feed, the JSON API,
authorization rules (for example, nobody can edit someone else's post), input validation,
XSS escaping and CSRF enforcement.

## Project structure

```
Network/                     # repository root
├── manage.py
├── requirements.txt
├── project4/                # Django project (settings, root URLs, WSGI/ASGI)
└── network/                 # Django app
    ├── models.py            # User (with following) and Post (with likes)
    ├── views.py             # pages + JSON API
    ├── forms.py             # PostForm (shared validation for create and edit)
    ├── urls.py
    ├── admin.py
    ├── tests.py
    ├── migrations/
    ├── management/commands/seed_demo.py
    ├── static/network/      # styles.css, network.js
    └── templates/network/   # layout, index, following, profile, login, register, partials
```

## Routes

### Pages

| Method | Path                  | Description                                  | Auth     |
|--------|-----------------------|----------------------------------------------|----------|
| GET    | `/`                   | All posts (paginated); POST creates a post   | Optional |
| GET    | `/following`          | Posts from followed users                    | Required |
| GET    | `/profile/<username>` | A user's profile and posts                   | Optional |
| GET/POST | `/login`, `/register` | Authentication                             |          |
| GET    | `/logout`             | Log out                                      |          |

### JSON API

Used by `static/network/network.js`. All endpoints require a logged-in session and a CSRF token
(`X-CSRFToken` header), and return JSON.

| Method | Path                               | Body                  | Success response                          |
|--------|------------------------------------|-----------------------|-------------------------------------------|
| PUT    | `/api/posts/<id>`                  | `{"content": "text"}` | The updated post (author only)            |
| POST   | `/api/posts/<id>/like`             | none                  | `{"liked": true, "likes": 3}`             |
| POST   | `/api/users/<username>/follow`     | none                  | `{"following": true, "followers": 12}`    |

Errors are returned as `{"error": "message"}` with status `400` (invalid input), `401` (not logged in),
`403` (not allowed), `404` (not found) or `405` (wrong method).

## Design notes

- **Authorization is enforced on the server.** Hiding the Edit button is only cosmetic; the API
  independently checks that the requester is the post's author.
- **XSS-safe rendering.** Django escapes all template output, and the JavaScript only writes user
  content with `textContent`, never `innerHTML`.
- **Efficient queries.** Like counts are annotated in the feed query, and the "liked by me" state for a
  whole page is resolved with one extra query instead of one per post.
- **Stable ordering.** Feeds are ordered explicitly by `-timestamp, -id`, so pagination is deterministic.
- **One source of validation.** `PostForm` validates both creating and editing posts.

## Configuration

Everything works with zero configuration for local development. For any other environment set:

| Variable               | Purpose                                                  | Default |
|------------------------|----------------------------------------------------------|---------|
| `DJANGO_DEBUG`         | `true` / `false`                                         | `true`  |
| `DJANGO_SECRET_KEY`    | Secret key (**required** when `DJANGO_DEBUG=false`)      | dev key |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames (required when debug is off)   | empty   |

When `DJANGO_DEBUG=false`, secure cookies are enabled. Before deploying, also run
`python manage.py check --deploy` and `python manage.py collectstatic`, and serve over HTTPS with a
production WSGI server such as gunicorn.

## Roadmap

- Delete posts
- Replies / comments
- Profile bios and avatars
- Infinite scroll
- REST API with token authentication

## Contributing

Issues and pull requests are welcome. Please run `python manage.py test` before opening a PR; CI runs
the same checks.

## License

Released under the [MIT License](LICENSE).

## Acknowledgements

Project specification and distribution code from
[CS50's Web Programming with Python and JavaScript](https://cs50.harvard.edu/web/) (Harvard University).
