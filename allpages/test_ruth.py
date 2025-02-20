import webbrowser
import json
import logging
import os
import re  # Import the regular expression module
import requests
import streamlit as st
from rauth import OAuth1Service
from logging.handlers import RotatingFileHandler
from urllib.parse import urlencode, urljoin  # Import urlencode

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
        consumer_key=os.environ.get("CONSUMER_KEY"),
        consumer_secret=os.environ.get("CONSUMER_SECRET"),
        request_token_url="https://api.etrade.com/oauth/request_token",
        access_token_url="https://api.etrade.com/oauth/access_token",
        authorize_url="https://us.etrade.com/e/t/etws/authorize?key={}&token={}",
        base_url="https://api.etrade.com"
    )

    base_url = os.environ.get("SANDBOX_BASE_URL", "https://apisb.etrade.com")
    st.warning("SANDBOX_BASE_URL environment variable not set. Using default.") if not os.environ.get("SANDBOX_BASE_URL") else None

    request_token, request_token_secret = etrade.get_request_token(params={"oauth_callback": "oob", "format": "json"})

    params = {
        'key': etrade.consumer_key,
        'token': request_token
    }
    query_string = urlencode(params)
    authorize_url = urljoin(etrade.authorize_url.split('?')[0], '?' + query_string)

    st.markdown(f"Please authorize your E*TRADE account by clicking [here]({authorize_url}).")
    verification_code = st.text_input("Enter the verification code from E*TRADE:", "")

    if st.button("Submit Verification Code"):
        if verification_code:
            # Sanitize the input *immediately*.  Keep only alphanumeric characters.
            verification_code = re.sub(r"[^a-zA-Z0-9]", "", verification_code).strip()
            logger.debug(f"Sanitized verification code: {verification_code}")

            if not verification_code:
                st.error("Verification code contained only invalid characters. Please try again.")
                return None, None

            try:
                # Pass the *sanitized* string directly to get_auth_session.
                # No encoding/decoding needed!
                session = etrade.get_auth_session(request_token, request_token_secret, params={"oauth_verifier": verification_code})
                st.success("Authentication successful!")
                return session, base_url
            except Exception as e:
                logger.error(f"Authentication error: {e}")
                st.error(f"Authentication error: {e}")
                return None, None
        else:
            st.error("Please enter a verification code.")
            return None, None
    return None, None

# Rest of your code (Market, Accounts, Order classes) remains the same...
class Market:
    def __init__(self, session, base_url):
        self.session = session
        self.base_url = base_url

    def quotes(self, symbol):
        url = self.base_url + f"/v1/market/quote/{symbol}.json"
        response = self.session.get(url)
        if response.status_code == 200:
            try:
                data = response.json()
                # Check if 'QuoteResponse' and 'QuoteData' exist and have at least one element
                if 'QuoteResponse' in data and 'QuoteData' in data['QuoteResponse'] and len(data['QuoteResponse']['QuoteData']) > 0:
                    quote_data = data['QuoteResponse']['QuoteData'][0]
                    # Check if 'Product' and 'All' exist
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
        response = self.session.get(url, header_auth=True)
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

    if session:
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
            account_list_response = accounts.session.get(account_list_url, header_auth=True)

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