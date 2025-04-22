from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlsplit, urljoin
import time
import ssl
import socket

app = Flask(__name__)
app.secret_key = 'super_secret_key'  # Wymagane dla Flask-Login

# Konfiguracja Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Symulacja bazy danych użytkowników
users = {'plyjak@studiofigura.com.pl': {'password': 'pip install lxml'}}

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    if username in users:
        return User(username)
    return None

def audit_seo(url):
    result = {
        "url": url,
        "title": "",
        "description": "",
        "headers": {"h1": [], "h2": [], "h3": [], "h4": [], "h5": [], "h6": []},
        "internal_links": [],
        "external_links": [],
        "https": False,
        "favicon": False,
        "robots_txt": False,
        "sitemap_xml": False,
        "missing_tags": [],
        "extra_tags": [],
        "html_size_kb": 0,
        "js_files_count": 0,
        "css_files_count": 0,
        "canonical_url": None,
        "open_graph_tags": [],
        "missing_og_tags": [],
        "twitter_tags": [],
        "missing_twitter_tags": [],
        "friendly_url": True,
        "viewport_meta_tag": False,
        "weak_anchors_count": 0,
        "empty_anchors_count": 0,
        "link_statuses": {},
        "robots_disallows": [],
        "sitemap_errors": [],
        "error": None,
        "load_time": 0,
        "resource_load_times": {},
        "images_without_alt": 0,
        "security": {
            "csp": False,
            "hsts": False,
            "ssl_valid": False,
            "ssl_expires_in": None,
            "ssl_issuer": None,
            "ssl_errors": []
        },
        "lazy_loading": {
            "img_count": 0,
            "img_lazy_count": 0,
            "iframe_count": 0,
            "iframe_lazy_count": 0
        },
        "webp_images": {
            "webp_count": 0,
            "webp_percentage": 0
        }
    }

    try:
        if not url.startswith("http"):
            raise ValueError("Nieprawidłowy adres URL. Upewnij się, że zaczyna się od http:// lub https://")

        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            )
        }

        start_time = time.time()
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        result["load_time"] = time.time() - start_time

        soup = BeautifulSoup(response.text, 'html.parser')
        parsed = urlparse(url)

        result["https"] = parsed.scheme == "https"
        result["title"] = soup.title.text.strip() if soup.title else "Brak"
        meta_desc = soup.find('meta', {'name': 'description'})
        result["description"] = (
            meta_desc['content'].strip()
            if meta_desc and 'content' in meta_desc.attrs
            else "Brak"
        )

        for tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            headers = soup.find_all(tag)
            result["headers"][tag] = [header.text.strip() for header in headers]

        base_url = f"{parsed.scheme}://{parsed.netloc}"
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(base_url, href)
            if parsed.netloc in full_url:
                result["internal_links"].append(full_url)
            elif full_url.startswith('http'):
                result["external_links"].append(full_url)

        all_links = result["internal_links"] + result["external_links"]
        for link in all_links:
            try:
                head = requests.head(link, timeout=5, allow_redirects=True, headers=headers)
                result["link_statuses"][link] = head.status_code
            except Exception:
                result["link_statuses"][link] = "Błąd"

        if soup.find('link', rel=lambda r: r and 'icon' in r.lower()):
            result["favicon"] = True

        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robots = requests.get(robots_url, headers=headers)
        result["robots_txt"] = robots.status_code == 200
        if robots.status_code == 200:
            for line in robots.text.splitlines():
                if line.strip().lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    result["robots_disallows"].append(path)

        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        sitemap = requests.get(sitemap_url, headers=headers)
        result["sitemap_xml"] = (sitemap.status_code == 200)
        result["sitemap_errors"] = []

        if sitemap.status_code == 200 and sitemap.text.strip().startswith('<?xml'):
            soup_sitemap = BeautifulSoup(sitemap.text, 'lxml-xml')
            loc_tags = soup_sitemap.find_all('loc')
            for loc in loc_tags[:30]:
                link = loc.text.strip()
                try:
                    r = requests.head(link, timeout=5, allow_redirects=True, headers=headers)
                    if r.status_code >= 400:
                        result["sitemap_errors"].append((link, r.status_code))
                except Exception:
                    result["sitemap_errors"].append((link, 'Błąd'))

        for tag in ['header','main','footer','article','section']:
            if not soup.find(tag):
                result["missing_tags"].append(tag)

        for tag in ['section','article']:
            cnt = len(soup.find_all(tag))
            if cnt > 1:
                result["extra_tags"].append(f"{tag} x {cnt}")

        result["html_size_kb"] = len(response.content) / 1024

        for script in soup.find_all('script', src=True):
            if script['src'].startswith('http'):
                result["js_files_count"] += 1
                start_time = time.time()
                requests.get(script['src'], timeout=10, headers=headers)
                result["resource_load_times"][script['src']] = time.time() - start_time

        for link in soup.find_all('link', href=True):
            if link['href'].endswith('.css') and link['href'].startswith('http'):
                result["css_files_count"] += 1
                start_time = time.time()
                requests.get(link['href'], timeout=10, headers=headers)
                result["resource_load_times"][link['href']] = time.time() - start_time

        canonical = soup.find('link', rel='canonical')
        result["canonical_url"] = canonical['href'] if canonical and 'href' in canonical.attrs else "Brak"

        for tag in ['og:title','og:description','og:image','og:url']:
            meta = soup.find('meta', property=tag)
            (result["open_graph_tags"] if meta else result["missing_og_tags"]).append(tag)

        for tag in ['twitter:card','twitter:title','twitter:description','twitter:image']:
            meta = soup.find('meta', attrs={'name':tag})
            (result["twitter_tags"] if meta else result["missing_twitter_tags"]).append(tag)

        path = urlsplit(url).path
        if any(ch in path for ch in ['?','=','&']):
            result["friendly_url"] = False

        if soup.find('meta', attrs={'name':'viewport'}):
            result["viewport_meta_tag"] = True

        weak = ['kliknij tutaj','tutaj','więcej','czytaj','sprawdź','kliknij','czytaj więcej']
        for a in soup.find_all('a', href=True):
            txt = a.get_text(strip=True).lower()
            if not txt:
                result["empty_anchors_count"] += 1
            elif txt in weak:
                result["weak_anchors_count"] += 1

        result["images_without_alt"] = 0
        for img in soup.find_all('img'):
            if not img.get('alt'):
                result["images_without_alt"] += 1

        result["security"]["csp"] = 'content-security-policy' in response.headers
        result["security"]["hsts"] = 'strict-transport-security' in response.headers

        if parsed.scheme == "https":
            try:
                context = ssl.create_default_context()
                with socket.create_connection((parsed.netloc, 443)) as sock:
                    with context.wrap_socket(sock, server_hostname=parsed.netloc) as ssock:
                        cert = ssock.getpeercert()
                        result["security"]["ssl_valid"] = True
                        result["security"]["ssl_issuer"] = dict(x[0][1] for x in ssl._ssl._test_decode_cert(cert))['issuer']
                        result["security"]["ssl_expires_in"] = ssl._ssl._test_decode_cert(cert)[0][0][9]
            except Exception as e:
                result["security"]["ssl_errors"].append(str(e))
        else:
            result["security"]["ssl_valid"] = False

        result["lazy_loading"]["img_count"] = len(soup.find_all('img'))
        result["lazy_loading"]["img_lazy_count"] = len(soup.find_all('img', loading="lazy"))
        result["lazy_loading"]["iframe_count"] = len(soup.find_all('iframe'))
        result["lazy_loading"]["iframe_lazy_count"] = len(soup.find_all('iframe', loading="lazy"))

        result["webp_images"]["webp_count"] = len([img for img in soup.find_all('img') if 'src' in img.attrs and img['src'].lower().endswith('.webp')])
        if result["webp_images"]["webp_count"] > 0:
            result["webp_images"]["webp_percentage"] = round((result["webp_images"]["webp_count"] / result["lazy_loading"]["img_count"]) * 100, 2)

    except Exception as e:
        result["error"] = str(e)

    return result

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = request.form['username']
            password = request.form['password']

            if username in users and users[username]['password'] == password:
                user = User(username)
                login_user(user)
                flash("Logowanie udane!", "success")
                return redirect(url_for('index'))
            else:
                flash("Niepoprawna nazwa użytkownika lub hasło.", "error")
        except KeyError as e:
            flash(f"Brakujące dane: {e}", "error")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        seo_data = audit_seo(request.form['url'])
        return render_template('report.html', seo_data=seo_data)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
