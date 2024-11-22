import os
from flask import Flask, redirect, url_for, session, request, jsonify, render_template
from authlib.integrations.flask_client import OAuth
import requests
from dotenv import load_dotenv
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Enforce HTTPS
app.config["PREFERRED_URL_SCHEME"] = "https"
Talisman(app, force_https=True)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Google OAuth Configurations
app.config["GOOGLE_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")
app.config["GOOGLE_DISCOVERY_URL"] = "https://accounts.google.com/.well-known/openid-configuration"

# Initialize OAuth client
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url=app.config["GOOGLE_DISCOVERY_URL"],
    client_kwargs={"scope": "email profile https://www.googleapis.com/auth/business.manage"},
)

# Airtable Configuration (use environment variables for security)
AIRTABLE_API_KEY = 'patrGInzrQiuBACnV.7283d83052558ebb51e72437c76cea77732bc61468461a86ef0a5f81fedaf1f0'
AIRTABLE_BASE_ID = 'appgXzBGcdhiuervR'
AIRTABLE_TABLE_NAME = 'All Merchants'

@app.route("/")
def index():
    return render_template("signin.html")

@app.route("/login")
def login():
    redirect_uri = url_for("authorize", _external=True)
    return google.authorize_redirect(
        redirect_uri, 
        prompt="consent", 
        access_type="offline",  # Offline ensures refresh token is granted
        include_granted_scopes="false"  # Forces reauthorization of all scopes
    )

@app.route("/authorize")
def authorize():
    token = google.authorize_access_token()
    access_token = token.get("access_token")

    if not access_token:
        return jsonify({"error": "Failed to retrieve access token"}), 400

    try:
        # Fetch user info manually using User Info API
        user_info = fetch_user_info(access_token)
        user_data = {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "token": token["id_token"],
        }
        gmb_id = fetch_gmb_id(token)
        user_data["GoogleBusinessId"] = gmb_id
        save_to_airtable(user_data)
        return redirect(url_for("success"))
    except Exception as e:
        return jsonify({"error": "Error processing user data", "details": str(e)}), 500

@app.route("/success")
def success():
    return redirect("https://www.fiveoutta5.com/thank-you")

def fetch_user_info(access_token):
    url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    raise Exception(f"Failed to fetch user info: {response.text}")

def fetch_gmb_id(token):
    url = "https://mybusinessbusinessinformation.googleapis.com/v1/accounts"
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
    }
    
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Error fetching GMB ID: {response.text}")

    data = response.json()
    
    if "accounts" in data:
        business_account = data["accounts"][0]
        return business_account.get("name")
    
    return "No GMB ID found"

def save_to_airtable(user_data):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "fields": {
            "Email": user_data["email"],
            "Name": user_data["name"],
            "GoogleBusinessId": user_data["GoogleBusinessId"],
            "ReviewManagementAllowed": True,
            "LeadSource": "Google Sign In"
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error saving to Airtable: {response.text}")
    return response.json()

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv("PORT", 8080)))
