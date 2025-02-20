import webbrowser
import json
import logging
import configparser
import requests
import streamlit as st
from rauth import OAuth1Service
from logging.handlers import RotatingFileHandler

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Logger setup
logger = logging.getLogger('etrade_logger')
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler("etrade.log", maxBytes=5 * 1024 * 1024, backupCount=3)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

def oauth():
    """Authenticate user via OAuth and return an authenticated session."""
    etrade = OAuth1Service(
        name="etrade",
        consumer_key=config["DEFAULT"]["CONSUMER_KEY"],
        consumer_secret=config["DEFAULT"]["CONSUMER_SECRET"],
        request_token_url="https://api.etrade.com/oauth/request_token",
        access_token_url="https://api.etrade.com/oauth/access_token",
        authorize_url="https://us.etrade.com/e/t/etws/authorize?key={}&token={}",
        base_url="https://api.etrade.com"
    )

    base_url = config["DEFAULT"]["PROD_BASE_URL"]  # Use production URL by default

    # Step 1: Get OAuth 1 request token
    request_token, request_token_secret = etrade.get_request_token(
        params={"oauth_callback": "oob", "format": "json"}
    )

    # Step 2: Open authorization URL for the user to authenticate
    authorize_url = etrade.authorize_url.format(etrade.consumer_key, request_token)
    st.write(f"Please authorize your E*TRADE account by clicking [here]({authorize_url}).")
    verification_code = st.text_input("Enter the verification code from E*TRADE:", "")

    if st.button("Submit Verification Code"):
        if verification_code:
            # Step 3: Exchange the verification code for an access token
            session = etrade.get_auth_session(
                request_token, request_token_secret, params={"oauth_verifier": verification_code}
            )
            st.success("Authentication successful!")
            return session, base_url
        else:
            st.error("Please enter a valid verification code.")
            return None, None
    return None, None
