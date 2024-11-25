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
    client_kwargs={"scope": "openid email profile"},  # Initial basic scopes
)

@app.route("/")
def index():
    return render_template("signin.html")

# Step 1: Basic Sign-In (email, profile, openid)
@app.route("/login")
def login():
    redirect_uri = url_for("authorize_basic", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/authorize-basic")
def authorize_basic():
    token = google.authorize_access_token()

    if not token or "access_token" not in token:
        return jsonify({"error": "Failed to retrieve basic token"}), 400

    # Save the basic token to the session
    session["basic_token"] = token["access_token"]
    session["id_token"] = token.get("id_token")

    # Redirect to request additional permissions
    return redirect(url_for("request_additional_scopes"))

# Step 2: Request Additional Scopes
@app.route("/request-scopes")
def request_additional_scopes():
    # Request additional permissions
    redirect_uri = url_for("authorize_additional", _external=True)
    google_scopes = "https://www.googleapis.com/auth/business.manage"
    return google.authorize_redirect(redirect_uri, scope=google_scopes)

@app.route("/authorize-additional")
def authorize_additional():
    token = google.authorize_access_token()

    if not token or "access_token" not in token:
        return jsonify({"error": "Failed to retrieve additional token"}), 400

    # Combine tokens if needed
    session["full_token"] = token

    # Fetch user info and GMB data
    try:
        access_token = token["access_token"]
        user_info = fetch_user_info(access_token)
        gmb_id = fetch_gmb_id(access_token)

        user_data = {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "GoogleBusinessId": gmb_id,
        }
        save_to_airtable(user_data)
        return redirect(url_for("success"))
    except Exception as e:
        return jsonify({"error": "Error processing user data", "details": str(e)}), 500

@app.route("/success")
def success():
    return redirect("https://www.fiveoutta5.com/thank-you")

# Fetch User Info
def fetch_user_info(access_token):
    url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    raise Exception(f"Failed to fetch user info: {response.text}")

# Fetch Google My Business ID
def fetch_gmb_id(access_token):
    url = "https://mybusinessbusinessinformation.googleapis.com/v1/accounts"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error fetching GMB ID: {response.text}")
    data = response.json()
    if "accounts" in data:
        return data["accounts"][0].get("name")
    return "No GMB ID found"

# Save User Data to Airtable
def save_to_airtable(user_data):
    AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
    AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
    AIRTABLE_TABLE_NAME = "All Merchants"

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "fields": {
            "Email": user_data["email"],
            "Name": user_data["name"],
            "GoogleBusinessId": user_data["GoogleBusinessId"],
            "ReviewManagementAllowed": True,
            "LeadSource": "Google Sign In",
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error saving to Airtable: {response.text}")
    return response.json()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
