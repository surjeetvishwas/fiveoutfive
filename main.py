import os
from flask import Flask, redirect, url_for, session, request, jsonify, render_template
from authlib.integrations.flask_client import OAuth
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")  # Use a secure secret key

# Configurations for Google OAuth
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
    client_kwargs={"scope": "openid email profile https://www.googleapis.com/auth/business.manage"},  # Added GMB scope
)

# Airtable Configuration (use environment variables for security)
AIRTABLE_API_KEY = 'patrGInzrQiuBACnV.7283d83052558ebb51e72437c76cea77732bc61468461a86ef0a5f81fedaf1f0'
AIRTABLE_BASE_ID = 'appgXzBGcdhiuervR'
AIRTABLE_TABLE_NAME = 'All Merchants'

@app.route("/")
def index():
    return render_template("signin.html")  # Render a simple page to sign in with Google

@app.route("/login")
def login():
    redirect_uri = url_for("authorize", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/authorize")
def authorize():
    # Get authorization token and user info
    token = google.authorize_access_token()
    user_info = token.get("userinfo")

    if not user_info:
        return jsonify({"error": "Failed to retrieve user info"}), 400

    user_data = {
        "email": user_info["email"],
        "name": user_info["name"],
        "token": token["id_token"]
    }

    # Fetch GMB ID
    gmb_id = fetch_gmb_id(token)

    # Now save this user data directly to Airtable
    try:
        user_data["GoogleBusinessId"] = gmb_id  # Add GMB ID to the data
        save_to_airtable(user_data)
        return redirect(url_for("success"))
    except Exception as e:
        return jsonify({"error": "Error processing user data", "details": str(e)}), 500

@app.route("/success")
def success():
    # Redirect to the thank you page on your Squarespace site
    return redirect("https://www.fiveoutta5.com/thank-you")

def fetch_gmb_id(token):
    """
    Fetch the Google My Business ID for the authenticated user.
    """
    # Make a request to the Google My Business API
    url = "https://mybusinessbusinessinformation.googleapis.com/v1/accounts"
    headers = {
        "Authorization": f"Bearer {token['access_token']}",  # Use the access token to authenticate
    }
    
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Error fetching GMB ID: {response.text}")

    data = response.json()
    
    # Extract the first business account ID (if it exists)
    if "accounts" in data:
        business_account = data["accounts"][0]
        return business_account.get("name")  # Return the account ID (or any other identifier)
    
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
            "GoogleBusinessId": user_data["GoogleBusinessId"],  # Save GMB ID
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
