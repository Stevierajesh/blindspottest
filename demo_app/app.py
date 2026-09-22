"""Demo application for BlindSpot.

Three pages, deliberately chosen:

  /profile           Page A — persistence works.
  /profile-broken    Page B — same UI, same "Saved successfully", but one
                     field is silently never written. The regression is
                     realistic: a single assignment is missing from the
                     handler, the request still returns success, and nothing
                     in the UI indicates a problem.
  /project-settings  Page C — different vocabulary ("Project title",
                     "Update Project"), same underlying invariant.

Page C is the one that matters for the argument. Without it, a reasonable
reader concludes BlindSpot is a hardcoded Bio test. With it, the system has to
recognize a persistent mutation it has never been told about.

Run:  python -m demo_app.app
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# Stand-in for a database. Module-level so it survives between requests.
DB = {
    "profile": {"name": "Stevie", "bio": "Hello"},
    "profile_broken": {"name": "Stevie", "bio": "Hello"},
    "project": {"title": "My Project", "description": "Internal tooling."},
}

_STYLE = """
  body { font-family: system-ui, sans-serif; max-width: 34rem; margin: 3rem auto;
         padding: 0 1rem; color: #1a1a1a; }
  label { display: block; margin: 1.2rem 0 .3rem; font-weight: 600; }
  input[type=text], textarea { width: 100%; padding: .5rem; font: inherit;
         border: 1px solid #bbb; border-radius: 4px; }
  textarea { min-height: 5rem; }
  button { margin-top: 1.4rem; padding: .55rem 1.1rem; font: inherit;
           border: 0; border-radius: 4px; background: #2563eb; color: #fff; }
  .flash { margin-top: 1rem; padding: .6rem .8rem; border-radius: 4px;
           background: #dcfce7; color: #14532d; }
  nav a { margin-right: 1rem; }
"""

_NAV = (
    '<nav><a href="/profile">Profile</a>'
    '<a href="/profile-broken">Profile (broken)</a>'
    '<a href="/project-settings">Project Settings</a></nav><hr>'
)


def _page(title: str, body: str, flash: bool) -> str:
    banner = '<p class="flash" role="status">Saved successfully</p>' if flash else ""
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>{title}</title><style>{_STYLE}</style></head><body>"
        f"{_NAV}<h1>{title}</h1>{banner}{body}</body></html>"
    )


def _profile_form(action: str, data: dict) -> str:
    return f"""
    <form method="POST" action="{action}">
      <label for="name">Name</label>
      <input type="text" id="name" name="name" value="{data['name']}">
      <label for="bio">Bio</label>
      <textarea id="bio" name="bio">{data['bio']}</textarea>
      <button type="submit">Save</button>
    </form>"""


def _project_form(data: dict) -> str:
    # Page C: different words for the same idea. Nothing here says "save",
    # "profile", or "bio".
    return f"""
    <form method="POST" action="/project-settings">
      <label for="title">Project title</label>
      <input type="text" id="title" name="title" value="{data['title']}">
      <label for="description">Description</label>
      <textarea id="description" name="description">{data['description']}</textarea>
      <button type="submit">Update Project</button>
    </form>"""


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------


def save_profile(form: dict) -> None:
    """Page A — correct."""
    DB["profile"]["name"] = form.get("name", [""])[0]
    DB["profile"]["bio"] = form.get("bio", [""])[0]


def save_profile_broken(form: dict) -> None:
    """Page B — the regression.

    A refactor moved the persistence calls around and the `bio` assignment was
    dropped. The handler still completes, still returns success, and the page
    still renders "Saved successfully". Name saves fine, which is what makes
    this hard to spot by hand: the feature looks like it works.
    """
    DB["profile_broken"]["name"] = form.get("name", [""])[0]
    # DB["profile_broken"]["bio"] = form.get("bio", [""])[0]   <- lost in refactor


def save_project(form: dict) -> None:
    """Page C — correct."""
    DB["project"]["title"] = form.get("title", [""])[0]
    DB["project"]["description"] = form.get("description", [""])[0]


ROUTES = {
    "/profile": ("Profile", lambda: _profile_form("/profile", DB["profile"]), save_profile),
    "/profile-broken": (
        "Profile",
        lambda: _profile_form("/profile-broken", DB["profile_broken"]),
        save_profile_broken,
    ),
    "/project-settings": (
        "Project Settings",
        lambda: _project_form(DB["project"]),
        save_project,
    ),
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(302)
            self.send_header("Location", "/profile")
            self.end_headers()
            return
        route = ROUTES.get(parsed.path)
        if not route:
            self.send_response(404)
            self.end_headers()
            return
        title, render, _ = route
        flash = "saved" in parse_qs(parsed.query)
        self._write(_page(title, render(), flash))

    def do_POST(self):
        route = ROUTES.get(urlparse(self.path).path)
        if not route:
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode())
        route[2](form)
        # Post/Redirect/Get, so a reload re-reads stored state rather than
        # re-submitting the form.
        self.send_response(303)
        self.send_header("Location", f"{self.path}?saved=1")
        self.end_headers()

    def _write(self, html: str) -> None:
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(port: int = 3000, background: bool = False) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), Handler)
    if background:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


LABELS = {
    "/profile": "Page A — persistence works",
    "/profile-broken": "Page B — says 'Saved successfully', drops Bio",
    "/project-settings": "Page C — different wording, same invariant",
}


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    port = int(args[0]) if args else 3000
    server = serve(port, background="--open" in sys.argv)

    print(f"\nBlindSpot demo app — http://127.0.0.1:{port}\n")
    for path, label in LABELS.items():
        print(f"  http://127.0.0.1:{port}{path}")
        print(f"      {label}\n")
    print("Ctrl-C to stop.\n")

    if "--open" in sys.argv:
        import webbrowser

        for path in LABELS:
            webbrowser.open(f"http://127.0.0.1:{port}{path}")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
    else:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
