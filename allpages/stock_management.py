# allpages/stock_management.py
import streamlit as st
import pandas as pd
import yfinance as yf
import logging
from datetime import datetime, date
from db import create_stock_table
from sqlalchemy import text  # Import the 'text' function

logger = logging.getLogger(__name__)

def stock_management_page(conn, user_id):
    """Main page function for stock management."""
    st.title("Stock Management")
    create_stock_table(conn) #create table if not exists

    page = st.sidebar.selectbox("Choose an action", ["View Stocks", "Add Stock"], key="stock_page_select")

    if page == "View Stocks":
        stock_list_page(conn, user_id)
    elif page == "Add Stock":
        add_stock_page(conn, user_id)

def get_stock_data(symbol, quantity, date_purchased, purchase_price):
    """Fetches stock data from yfinance and adds extra fields."""
    try:
        stock = yf.Ticker(symbol)
        stock_info = stock.info
        stock_info['quantity'] = quantity
        stock_info['date_purchased'] = date_purchased
        stock_info['purchase_price'] = purchase_price
        return stock_info
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {str(e)}")
        st.error(f"Could not retrieve data for {symbol}.  Check the symbol and try again.  Error: {e}")  # User-friendly error
        return None
        #You can return default value as per the requirement.

def add_stock_to_db(conn, user_id, symbol, name, quantity, date_purchased, purchase_price, date_sold=None, sold_price=None, comments=None, source=None):
    """Adds a stock to the database."""
    try:
        with conn.begin() as trans:
            conn.execute(
                text("""
                INSERT INTO stocks (user_id, symbol, name, quantity, date_purchased, date_sold, purchase_price, sold_price, comments, source)
                VALUES (:user_id, :symbol, :name, :quantity, :date_purchased, :date_sold, :purchase_price, :sold_price, :comments, :source)
                ON CONFLICT (user_id, symbol) DO UPDATE
                SET quantity = EXCLUDED.quantity,  -- Update relevant fields on conflict
                    date_purchased = EXCLUDED.date_purchased,
                    purchase_price = EXCLUDED.purchase_price,
                    date_sold = EXCLUDED.date_sold,
                    sold_price = EXCLUDED.sold_price,
                    comments = EXCLUDED.comments,
                    name = EXCLUDED.name,
                    source = EXCLUDED.source;
                """),
                {
                    "user_id": user_id,
                    "symbol": symbol,
                    "name": name,
                    "quantity": quantity,
                    "date_purchased": date_purchased,
                    "date_sold": date_sold,
                    "purchase_price": purchase_price,
                    "sold_price": sold_price,
                    "comments": comments,
                    "source" : source
                }
            )
            trans.commit()
            return True
    except Exception as e:
        logger.exception(f"Error adding stock to database: {e}")
        st.error(f"Error adding stock to database: {e}") # Inform the user.
        return False

def get_user_stocks(conn, user_id):
    """Retrieves all stocks for a given user from the database."""
    try:
        query = text("SELECT * FROM stocks WHERE user_id = :user_id")
        df = pd.read_sql_query(query, conn, params={"user_id": user_id})
        # Convert date columns to datetime objects (important for display)
        if not df.empty:
            df['date_purchased'] = pd.to_datetime(df['date_purchased']).dt.date
            df['date_sold'] = pd.to_datetime(df['date_sold']).dt.date
        return df
    except Exception as e:
        logger.exception(f"Error retrieving user stocks: {e}")
        st.error(f"Error retrieving stock data: {e}") # User-friendly error
        return pd.DataFrame()  # Return an empty DataFrame on error

def stock_list_page(conn, user_id):
    """Displays the list of stocks."""
    st.header("Your Stocks")
    #create_stock_table(conn) # No need: Called in main stock management page
    stocks_df = get_user_stocks(conn, user_id)
    stocks_data = []

    for _, row in stocks_df.iterrows():
        stock_info = get_stock_data(row['symbol'], row['quantity'], row['date_purchased'], row['purchase_price'])
        if stock_info:
            stocks_data.append(stock_info)

    if stocks_data:
            stocks_df_yf = pd.DataFrame(stocks_data)
            display_cols = ['symbol', 'shortName', 'quantity', 'date_purchased', 'purchase_price', 'currentPrice', 'regularMarketChange', 'regularMarketChangePercent']
            filtered_cols = [col for col in display_cols if col in stocks_df_yf.columns]
            st.dataframe(stocks_df_yf[filtered_cols])
    elif not stocks_df.empty :
        # If we have data in *our* database, but yfinance failed, still show *something*.
        display_cols = ['symbol', 'name', 'quantity', 'date_purchased', 'purchase_price', 'date_sold', 'sold_price', 'comments']
        st.dataframe(stocks_df[display_cols])
    else:
        st.write("You have no stocks yet.")

def add_stock_page(conn, user_id):
    """Provides a form to add a new stock."""
    st.header("Add Stock")
    #create_stock_table(conn)  # No need: Called in main stock management page.

    with st.form("add_stock_form"):
        symbol = st.text_input("Symbol", max_chars=10).upper()
        name = st.text_input("Name", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        date_purchased = st.date_input("Date Purchased")
        purchase_price = st.number_input("Purchase Price", min_value=0.01, step=0.01, format="%.2f")
        date_sold = st.date_input("Date Sold", value=None)
        sold_price = st.number_input("Sold Price", min_value=0.0, step=0.01, format="%.2f", value=0.0)  # Allow empty
        comments = st.text_area("Comments")
        source = st.text_input("Source")

        submitted = st.form_submit_button("Add Stock")

        if submitted:
            if not symbol:
                st.error("Symbol is required.")
                return
            date_purchased_str = date_purchased.strftime('%Y-%m-%d') if date_purchased else None
            date_sold_str = date_sold.strftime('%Y-%m-%d') if date_sold else None
            sold_price_value = sold_price if sold_price >0 else None #handle if sold price not entered

            success = add_stock_to_db(conn, user_id, symbol, name, quantity, date_purchased_str, purchase_price, date_sold_str, sold_price_value, comments,source)
            if success:
                st.success(f"Added/Updated {symbol} to your stocks!")
                #st.balloons()