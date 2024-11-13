import os
from flask import Flask, redirect, url_for, session, request, jsonify, render_template
from authlib.integrations.flask_client import OAuth
import requests

app = Flask(__name__)
app.secret_key = 'random_secret_key'  # Replace with a secure secret key

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
    client_kwargs={"scope": "openid email profile"},
)

# Backend API URL (Replace with your actual Cloud Run service URL)
CLOUD_RUN_API_URL = "https://google-business-889678371878.us-central1.run.app/process-user"

@app.route("/")
def index():
    return render_template("signin.html")  # Render the Sign-in with Google page

@app.route("/login")
def login():
    redirect_uri = url_for("authorize", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/authorize")
def authorize():
    token = google.authorize_access_token()
    user_info = token.get("userinfo")

    if not user_info:
        return jsonify({"error": "Failed to retrieve user info"}), 400

    user_data = {
        "email": user_info["email"],
        "name": user_info["name"],
        "token": token["id_token"]
    }

    try:
        response = requests.post(CLOUD_RUN_API_URL, json=user_data)
        response_data = response.json()

        if response.status_code == 200 and response_data.get("success"):
            return redirect(url_for("success"))

        return jsonify({"error": "Failed to save data", "details": response_data}), response.status_code

    except Exception as e:
        return jsonify({"error": "Error processing user data", "details": str(e)}), 500

@app.route("/success")
def success():
    return "User data saved successfully in Airtable!"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
