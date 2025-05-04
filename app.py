import sys
import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_session import Session
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlsplit, urljoin
import time
import ssl
import socket
from datetime import datetime, timezone
from OpenSSL import crypto
import logging

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# Konfiguracja Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_session/'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
Session(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

users = {'plyjak@studiofigura.com.pl': {'password': 'AudytSEO2025!'}}

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    if username in users:
        return User(username)
    return None

# Ustaw domyślne kodowanie na UTF-8
os.environ["PYTHONIOENCODING"] = "utf-8"

# Konfiguracja logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        "load_time": 0.0,
        "resource_load_times": {},
        "images_without_alt": 0,
        "security": {
            "csp": False,
            "hsts": False,
            "ssl_valid": False,
            "ssl_issuer": None,
            "ssl_expires_in": None,
            "ssl_errors": []
        },
        "lazy_loading": {
            "img_count": 0,
            "img_lazy_count": 0,
            "iframe_count": 0,
            "iframe_lazy_count": 0
        },
        "webp_images": {},
        "h1_present": False
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
        try:
            response = requests.get(url, timeout=10, headers=headers, allow_redirects=True)
            response.raise_for_status()
            final_url = response.url  # Użyj końcowego URL po ewentualnych przekierowaniach
            result["load_time"] = float(time.time() - start_time)
            logging.info(f"Żądanie GET dla {url} zakończone sukcesem, status: {response.status_code}")
        except requests.RequestException as e:
            result["error"] = str(e)
            result["load_time"] = 0.0
            logging.error(f"Błąd żądania dla {url}: {e}")
            return result

        soup = BeautifulSoup(response.text, 'html.parser')
        parsed = urlparse(final_url)

        result["https"] = parsed.scheme == "https"
        result["title"] = soup.title.text.strip() if soup.title else "Brak"
        meta_desc = soup.find('meta', {'name': 'description'})
        result["description"] = meta_desc['content'].strip() if meta_desc and 'content' in meta_desc.attrs else "Brak"

        for tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            headers = soup.find_all(tag)
            result["headers"][tag] = [header.text.strip() for header in headers if header.text.strip()]
            if tag == 'h1' and headers:
                result["h1_present"] = True

        base_url = f"{parsed.scheme}://{parsed.netloc}"
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(base_url, href)
            if parsed.netloc in full_url:
                result["internal_links"].append(full_url)
            elif full_url.startswith('http'):
                result["external_links"].append(full_url)

        all_links = result["internal_links"] + result["external_links"]
        for link in all_links[:50]:
            try:
                head = requests.head(link, timeout=5, allow_redirects=True, headers=headers)
                result["link_statuses"][link] = head.status_code
            except Exception:
                result["link_statuses"][link] = "Błąd"

        favicon_links = soup.find_all('link', rel=lambda r: r and 'icon' in r.lower())
        result["favicon"] = bool(favicon_links)

        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            robots = requests.get(robots_url, timeout=5, headers=headers)
            result["robots_txt"] = robots.status_code == 200
            if robots.status_code == 200:
                for line in robots.text.splitlines():
                    if line.strip().lower().startswith("disallow:"):
                        path = line.split(":", 1)[1].strip()
                        result["robots_disallows"].append(path)
        except Exception as e:
            result["robots_txt"] = False
            logging.error(f"Błąd pobierania robots.txt dla {url}: {e}")

        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        try:
            sitemap = requests.get(sitemap_url, timeout=5, headers=headers)
            result["sitemap_xml"] = sitemap.status_code == 200
            if sitemap.status_code == 200 and sitemap.text.strip().startswith('<?xml'):
                soup_sitemap = BeautifulSoup(sitemap.text, 'lxml-xml')
                loc_tags = soup_sitemap.find_all('loc')
                for loc in loc_tags[:30]:
                    link = loc.text.strip()
                    try:
                        r = requests.head(link, timeout=5, allow_redirects=True, headers=headers)
                        if r.status_code >= 400:
                            result["sitemap_errors"].append((link, r.status_code))
                    except Exception as e:
                        result["sitemap_errors"].append((link, 'Błąd'))
                        logging.error(f"Błąd sprawdzania linku z sitemap.xml: {link}, {e}")
        except Exception as e:
            result["sitemap_xml"] = False
            logging.error(f"Błąd pobierania sitemap.xml dla {url}: {e}")

        for tag in ['header', 'main', 'footer', 'article', 'section']:
            if not soup.find(tag):
                result["missing_tags"].append(tag)

        for tag in ['section', 'article']:
            cnt = len(soup.find_all(tag))
            if cnt > 1:
                result["extra_tags"].append(f"{tag} x {cnt}")

        result["html_size_kb"] = len(response.content) / 1024

        for script in soup.find_all('script', src=True):
            if script['src'].startswith('http'):
                result["js_files_count"] += 1
                try:
                    start_time = time.time()
                    requests.get(script['src'], timeout=5, headers=headers)
                    result["resource_load_times"][script['src']] = time.time() - start_time
                except Exception as e:
                    result["resource_load_times"][script['src']] = "Błąd"
                    logging.error(f"Błąd pobierania pliku JS: {script['src']}, {e}")

        for link in soup.find_all('link', href=True):
            if link['href'].endswith('.css') and link['href'].startswith('http'):
                result["css_files_count"] += 1
                try:
                    start_time = time.time()
                    requests.get(link['href'], timeout=5, headers=headers)
                    result["resource_load_times"][link['href']] = time.time() - start_time
                except Exception as e:
                    result["resource_load_times"][link['href']] = "Błąd"
                    logging.error(f"Błąd pobierania pliku CSS: {link['href']}, {e}")

        canonical_links = soup.find_all('link', rel='canonical')
        result["canonical_url"] = canonical_links[0]['href'] if canonical_links and 'href' in canonical_links[0].attrs else "Brak"

        for tag in ['og:title', 'og:description', 'og:image', 'og:url']:
            meta = soup.find('meta', property=tag)
            (result["open_graph_tags"] if meta else result["missing_og_tags"]).append(tag)

        for tag in ['twitter:card', 'twitter:title', 'twitter:description', 'twitter:image']:
            meta = soup.find('meta', attrs={'name': tag})
            (result["twitter_tags"] if meta else result["missing_twitter_tags"]).append(tag)

        path = urlsplit(url).path
        if any(ch in path for ch in ['?', '=', '&']):
            result["friendly_url"] = False

        viewport_meta = soup.find('meta', attrs={'name': 'viewport'})
        result["viewport_meta_tag"] = bool(viewport_meta)

        weak = ['kliknij tutaj', 'tutaj', 'więcej', 'czytaj', 'sprawdź', 'kliknij', 'czytaj więcej']
        for a in soup.find_all('a', href=True):
            txt = a.get_text(strip=True).lower()
            if not txt:
                result["empty_anchors_count"] += 1
            elif txt in weak:
                result["weak_anchors_count"] += 1

        result["images_without_alt"] = sum(1 for img in soup.find_all('img') if not img.get('alt'))

        result["security"]["csp"] = 'content-security-policy' in response.headers
        result["security"]["hsts"] = 'strict-transport-security' in response.headers

        if parsed.scheme == "https":
            try:
                context = ssl.create_default_context()
                with socket.create_connection((parsed.netloc, 443), timeout=5) as sock:
                    with context.wrap_socket(sock, server_hostname=parsed.netloc) as ssock:
                        cert = ssock.getpeercert(binary_form=True)
                        x509 = crypto.load_certificate(crypto.FILETYPE_ASN1, cert)
                        issuer = x509.get_issuer()
                        result["security"]["ssl_issuer"] = issuer.get_components()[-1][-1].decode('utf-8')
                        expiry_date = datetime.strptime(x509.get_notAfter().decode('ascii'), '%Y%m%d%H%M%SZ')
                        result["security"]["ssl_expires_in"] = expiry_date.strftime('%Y-%m-%d %H:%M:%S')
                        now = datetime.utcnow()
                        result["security"]["ssl_valid"] = expiry_date > now
                        if not result["security"]["ssl_valid"]:
                            result["security"]["ssl_errors"].append("Certyfikat wygasł")
            except ssl.SSLError as ssl_err:
                result["security"]["ssl_valid"] = False
                result["security"]["ssl_errors"].append(f"Błąd SSL: {ssl_err}")
                logging.error(f"Błąd SSL dla {url}: {ssl_err}")
            except Exception as e:
                result["security"]["ssl_valid"] = False
                result["security"]["ssl_errors"].append(f"Błąd: {e}")
                logging.error(f"Błąd podczas sprawdzania certyfikatu SSL dla {url}: {e}")
        else:
            result["security"]["ssl_valid"] = False
            result["security"]["ssl_errors"].append("Strona nie używa HTTPS")

        result["lazy_loading"]["img_count"] = len(soup.find_all('img'))
        result["lazy_loading"]["img_lazy_count"] = len(soup.find_all('img', loading="lazy"))
        result["lazy_loading"]["iframe_count"] = len(soup.find_all('iframe'))
        result["lazy_loading"]["iframe_lazy_count"] = len(soup.find_all('iframe', loading="lazy"))

        image_extensions = [".webp", ".jpg", ".png"]
        image_counts = {ext: 0 for ext in image_extensions}
        total_images = result["lazy_loading"]["img_count"]
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                for ext in image_extensions:
                    if src.lower().endswith(ext):
                        image_counts[ext] += 1
                        break
        result["webp_images"] = {
            ext: {
                "count": count,
                "percentage": round((count / total_images * 100), 2) if total_images > 0 else 0
            } for ext, count in image_counts.items()
        }

        logging.info(f"Audyt zakończony dla {url}, title: {result['title']}")
    except Exception as e:
        result["error"] = str(e)
        result["load_time"] = 0.0
        logging.error(f"Błąd ogólny w audit_seo dla {url}: {e}")

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
                logging.info(f"Użytkownik {username} zalogowany pomyślnie.")
                return redirect(url_for('index'))
            else:
                flash("Niepoprawna nazwa użytkownika lub hasło.", "error")
                logging.warning(f"Nieudana próba logowania dla użytkownika {username}.")
        except KeyError as e:
            flash(f"Brakujące dane: {e}", "error")
            logging.error(f"Błąd podczas logowania: {e}")
    return render_template('login.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('user_id', None)  # Usuń dane użytkownika z sesji
    session.clear()  # Opcjonalnie: wyczyść całą sesję
    return redirect(url_for('login'))  # Przekieruj na stronę logowania

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        url = request.form.get('url')
        if not url:
            return jsonify({"error": "Brak adresu URL"}), 400

        # Czyszczenie poprzednich danych z sesji
        if 'seo_data' in session:
            logging.info(f"Usuwanie starych danych sesji dla: {session['seo_data']['url']}")
            session.pop('seo_data')

        seo_data = audit_seo(url)
        logging.info(f"Nowe dane audytu dla: {url}, title: {seo_data['title']}")
        if seo_data.get('error'):
            logging.error(f"Błąd audytu: {seo_data['error']}")
            return jsonify({"error": seo_data['error']}), 500

        # Zapisanie nowych danych do sesji
        session['seo_data'] = seo_data
        session.modified = True
        logging.info(f"Zapisano w sesji: {session['seo_data']['url']}, title: {seo_data['title']}")
        return jsonify({"status": "success"}), 200

    response = render_template('index.html')
    response = app.make_response(response)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/report')
@login_required
def report():
    # Sprawdzanie, czy dane istnieją w sesji
    seo_data = session.get('seo_data', None)
    if not seo_data:
        logging.error("Brak danych SEO w sesji!")
        flash('Brak danych audytu. Wykonaj audyt ponownie.', 'error')
        return redirect(url_for('index'))

    logging.info(f"Generowanie raportu dla: {seo_data['url']}, title: {seo_data['title']}")
    response = render_template('report.html', seo_data=seo_data)
    response = app.make_response(response)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    app.run(debug=True)
