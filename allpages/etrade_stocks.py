import webbrowser
import json
import logging
import os
import re
import requests
import streamlit as st
from requests_oauthlib import OAuth1  # Import OAuth1 from requests_oauthlib
from logging.handlers import RotatingFileHandler
from urllib.parse import urlencode, urljoin, parse_qs

# Logger setup (keep this as is)
logger = logging.getLogger('etrade_logger')
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler("etrade.log", maxBytes=5 * 1024 * 1024, backupCount=3)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

def oauth():
    """Authenticate user via OAuth and return an authenticated session."""

    consumer_key = os.environ.get("CONSUMER_KEY")
    consumer_secret = os.environ.get("CONSUMER_SECRET")
    base_url = os.environ.get("PROD_BASE_URL", "https://api.etrade.com")

    if not consumer_key or not consumer_secret:
        logger.error("Consumer key or secret not set in environment variables.")
        st.error("Consumer key or secret not set in environment variables.")
        return None, None

    logger.debug(f"Consumer Key: {consumer_key}")
    logger.debug(f"Consumer Secret: {consumer_secret}")
    logger.debug(f"Base URL: {base_url}")

    st.warning("PROD_BASE_URL not set") if not os.environ.get("PROD_BASE_URL") else None

    request_token_url = base_url + "/oauth/request_token"
    access_token_url = base_url + "/oauth/access_token"
    authorize_url = "https://us.etrade.com/e/t/etws/authorize"  # No {} placeholders

    # 1. Get Request Token
    if "request_token" not in st.session_state:
        oauth = OAuth1(consumer_key, client_secret=consumer_secret,
                    callback_uri='oob',)  # Use 'oob' for out-of-band
        r = requests.post(url=request_token_url, auth=oauth, params={'format': 'json'})
        r.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        credentials = parse_qs(r.text)
        request_token = credentials.get('oauth_token')[0]
        request_token_secret = credentials.get('oauth_token_secret')[0]
   
        logger.debug("SET request_token and request_token_secret in session")
        st.session_state["request_token"] = request_token
        st.session_state["request_token_secret"] = request_token_secret
    else:
        request_token = st.session_state["request_token"]
        request_token_secret = st.session_state["request_token_secret"]

    # logger.debug(f"Credentials after parse_qs: {credentials}")
    logger.debug(f"Request Token: {st.session_state['request_token']}")
    logger.debug(f"Request Token Secret: {st.session_state['request_token']}")

    # 2. Authorize
    params = {
        'key': consumer_key,
        'token': request_token
    }
    query_string = urlencode(params)
    auth_url = urljoin(authorize_url, '?' + query_string)

    st.markdown(f"Please authorize your E*TRADE account by clicking [here]({auth_url}).")
    verification_code = st.text_input("Enter the verification code from E*TRADE:", "")

    if st.button("Submit Verification Code"):
        if verification_code:
            verification_code = re.sub(r"[^a-zA-Z0-9]", "", verification_code).strip()
            logger.debug(f"Sanitized verification code: {verification_code}")

            if not verification_code:
                st.error("Verification code invalid")
                return None, None

            # 3. Get Access Token
            logger.debug("---- Access Token Request Details ----")
            logger.debug(f"Consumer Key: {consumer_key}")
            logger.debug(f"Consumer Secret: {consumer_secret}")
            logger.debug(f"Request Token: {request_token}")
            logger.debug(f"Request Token Secret: {request_token_secret}")
            logger.debug(f"Verification Code: {verification_code}")

            try:
                oauth = OAuth1(consumer_key,
                               client_secret=consumer_secret,
                               resource_owner_key=st.session_state["request_token"],
                               resource_owner_secret=st.session_state["request_token_secret"],
                               verifier=verification_code)
                r = requests.post(url=access_token_url, auth=oauth)
                r.raise_for_status()

                credentials = parse_qs(r.text)
                access_token = credentials.get('oauth_token')[0]
                access_token_secret = credentials.get('oauth_token_secret')[0]

                logger.debug(f"Access Token: {access_token}")
                logger.debug(f"Access Token Secret: {access_token_secret}")

                # Create a session (using requests.Session)
                session = requests.Session()
                session.auth = OAuth1(consumer_key,
                                     client_secret=consumer_secret,
                                     resource_owner_key=access_token,
                                     resource_owner_secret=access_token_secret)

                st.success("Authentication successful!")
                return session, base_url

            except requests.exceptions.RequestException as e:
                logger.error(f"Authentication error: {e}")
                if "401" in str(e): # Example: Check for 401 Unauthorized (adjust based on actual errors)
                    st.error(f"Authentication error: Invalid Consumer Key or Secret. Please double-check your environment variables.")
                    logger.error(f"Authentication error: Invalid Consumer Key or Secret. Please double-check your environment variables.")
                elif "verification_code" in str(e): # Example: Error might mention verification code
                    st.error(f"Authentication error: Problem with verification code. Ensure you copied it correctly from the E*TRADE authorization page.")
                    logger.error(f"Authentication error: Problem with verification code. Ensure you copied it correctly from the E*TRADE authorization page.")
                else:
                    st.error(f"Authentication error: {e}. Check the logs for more details (etrade.log).")
                    logger.error(f"Authentication error: {e}")
                return None, None

        else:
            st.error("Please enter verification")
            return None, None

    return None, None

# Example of using the session (modify your Market, Accounts, etc. classes)
class Market:
    def __init__(self, session, base_url):
        self.session = session
        self.base_url = base_url

    def quotes(self, symbol):
        url = self.base_url + f"/v1/market/quote/{symbol}.json"
        response = self.session.get(url)  # Use the session here
        if response.status_code == 200:
            try:
                data = response.json()
                if 'QuoteResponse' in data and 'QuoteData' in data['QuoteResponse'] and len(data['QuoteResponse']['QuoteData']) > 0:
                    quote_data = data['QuoteResponse']['QuoteData'][0]
                    if 'Product' in quote_data and 'All' in quote_data:
                        st.write(f"Stock Symbol: {quote_data['Product']['symbol']}")
                        st.write(f"Last Price: ${quote_data['All']['lastTrade']}")
                    else:
                        st.error("Unexpected response format: Missing 'Product' or 'All' data.")
                else:
                    st.error("Unexpected response format: Missing 'QuoteResponse' or 'QuoteData'.")
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                st.error(f"Error parsing response: {e}")
                logger.error(f"Error parsing quote response: {response.text}, Error: {e}")
        elif response.status_code == 204:
            st.write("The requested Symbol is not found")
        else:
            st.error(f"Error fetching quote: Status Code {response.status_code}")
            logger.error(f"Error fetching quote for {symbol}: {response.status_code} - {response.text}")

class Accounts:
    def __init__(self, session, base_url):
        self.session = session
        self.base_url = base_url

    def portfolio(self):
        url = self.base_url + "/v1/accounts/list.json"
        response = self.session.get(url)  # Use the session here
        if response.status_code == 200:
            st.write("Portfolio data retrieved successfully.")
            logger.info(f"Portfolio data: {response.text}")
        else:
            st.error(f"Error fetching portfolio: Status Code {response.status_code}")
            logger.error(f"Error fetching portfolio: {response.status_code} - {response.text}")

class Order:
    def __init__(self, session, account_id_key, base_url):
        self.session = session
        self.account_id_key = account_id_key  # Corrected: Use a single account ID
        self.base_url = base_url

    def preview_order(self):
        st.write("Order preview is currently not implemented.")

    def place_order(self):
        st.write("Order placement is currently not implemented.")

def etrade_stocks_page(conn=None):
    """Streamlit page for managing E-Trade stocks"""
    st.title("E-Trade Stock Trading")
    session, base_url = oauth()
    
    logger.debug(f"Session: {session}")
    logger.debug(f"Base URL: {base_url}")
    if session:
        logger.info("Session created successfully. Ready to make API calls.")
        option = st.sidebar.selectbox("Select Option", ["Market Quotes", "Portfolio", "Place Order"])

        if option == "Market Quotes":
            st.subheader("Get Stock Quotes")
            symbol = st.text_input("Enter Stock Symbol", "AAPL")
            if st.button("Get Quote"):
                market = Market(session, base_url)
                market.quotes(symbol)

        elif option == "Portfolio":
            st.subheader("View Portfolio")
            accounts = Accounts(session, base_url)
            accounts.portfolio()

        elif option == "Place Order":
            st.subheader("Place a Stock Order")

            # Get account list to select from (you'll need this for placing orders)
            accounts = Accounts(session, base_url)  # You might want to cache this
            account_list_url = base_url + "/v1/accounts/list.json"
            account_list_response = accounts.session.get(account_list_url)

            if account_list_response.status_code == 200:
                try:
                    account_data = account_list_response.json()
                    # Extract accountIdKey values and descriptions for the selectbox
                    account_ids = [account['accountIdKey'] for account in account_data['AccountListResponse']['Accounts']['Account']]
                    account_descriptions = [f"{account['accountDesc']} ({account['accountId']})" for account in account_data['AccountListResponse']['Accounts']['Account']]
                    # Combine descriptions and IDs for the selectbox
                    account_options = [f"{desc} - {id_key}" for desc, id_key in zip(account_descriptions, account_ids)]

                    # Use the combined descriptions and IDs in the selectbox
                    selected_account_option = st.selectbox("Select Account", account_options)

                    # Extract the accountIdKey from the selected option
                    selected_account_id_key = selected_account_option.split(" - ")[-1]


                    order = Order(session, selected_account_id_key, base_url)  # Pass the selected account
                    order.preview_order()
                    if st.button("Submit Order"):
                        order.place_order()
                except (KeyError, json.JSONDecodeError) as e:
                    st.error(f"Error parsing account list: {e}")
                    logger.error(f"Error parsing account list response: {account_list_response.text}, Error: {e}")
            else:
                st.error(f"Error fetching account list: Status code {account_list_response.status_code}")
                logger.error(f"Error fetching account list: {account_list_response.status_code} - {account_list_response.text}")

    else:
        st.warning("Please complete authentication first.")

if __name__ == '__main__':
    etrade_stocks_page()