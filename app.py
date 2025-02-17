# app.py
import streamlit as st
import logging  # Import the logging module
from db import create_tables, get_db_connection
from allpages.calorie_counter import calorie_counter_page
from allpages.exercise_master import exercise_master_page
from allpages.stock_management import stock_management_page

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,  # Set the minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",  # Define the log message format
    # Optional:  Log to a file (in addition to the console)
    # filename="app.log",
    # filemode="a",  # Append to the log file
)
logger = logging.getLogger(__name__) # Get a logger instance


st.set_page_config(page_title="Calorie Counter App", layout="wide")

st.sidebar.title("Navigation")
page = st.sidebar.radio("Select a page", ["Calorie Counter", "Exercise Master", "Stock Management"])

conn = get_db_connection()
if conn:
    create_tables(conn)
    conn.close()
else:
    st.error("Could not connect to the database.")
    logger.error("Could not connect to the database.")  # Log database connection errors


if page == "Calorie Counter":
    calorie_counter_page()
elif page == "Exercise Master":
    exercise_master_page()
elif page == "Stock Management":
    stock_management_page()