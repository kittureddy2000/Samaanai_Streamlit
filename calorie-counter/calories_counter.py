import streamlit as st
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text  # Import text
import os
from datetime import date, timedelta
import plotly.express as px

# Database connection (using environment variables for security)
db_user = os.environ.get("DB_USER", "postgres")
db_pass = os.environ.get("DB_PASS", "password")
db_name = os.environ.get("DB_NAME", "calorie_db")
db_host = os.environ.get("DB_HOST", "localhost")  # This will be the Cloud SQL instance connection name
db_port = os.environ.get("DB_PORT", "5432")  # Default Postgres port


# --- Database Functions ---
def get_db_connection():
    """Creates a database connection."""
    try:
        engine = create_engine(f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}")
        conn = engine.connect()
        return conn
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        return None

def create_tables(conn):
    """Creates the necessary tables if they don't exist."""
    try:
        with conn.execution_options(isolation_level="AUTOCOMMIT").begin() as trans:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS calorie_intake (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    breakfast INT,
                    lunch INT,
                    dinner INT,
                    exercise INT,
                    UNIQUE(date)
                );
            """))

    except Exception as e:
        st.error(f"Error creating tables: {e}")

def insert_calorie_data(conn, breakfast, lunch, dinner, exercise, intake_date):
    """Inserts calorie data for a given date."""
    try:
        with conn.begin() as trans:
            conn.execute(
                text("""INSERT INTO calorie_intake (date, breakfast, lunch, dinner, exercise)
                     VALUES (:date, :breakfast, :lunch, :dinner, :exercise)
                     ON CONFLICT (date) DO UPDATE
                     SET breakfast = EXCLUDED.breakfast,
                         lunch = EXCLUDED.lunch,
                         dinner = EXCLUDED.dinner,
                         exercise = EXCLUDED.exercise"""),
                {"date": intake_date, "breakfast": breakfast, "lunch": lunch, "dinner": dinner, "exercise": exercise}
            )
        st.success("Data saved successfully!")
    except Exception as e:
        st.error(f"Error inserting data: {e}")

def get_calorie_data(conn, start_date, end_date):
    """Retrieves calorie data within a date range."""
    try:
        query = text(f"""
            SELECT id, CAST(date as DATE), breakfast, lunch, dinner, exercise FROM calorie_intake
            WHERE date >= :start_date AND date <= :end_date
            ORDER BY date;
        """)
        df = pd.read_sql_query(query, conn, params={"start_date":start_date, "end_date":end_date})
        return df
    except Exception as e:
        st.error(f"Error retrieving data: {e}")
        return pd.DataFrame()


# --- Streamlit App ---

st.title("Calorie Counter")

# Input Section
intake_date = st.date_input("Date", date.today())
breakfast = st.number_input("Breakfast Calories", min_value=0, step=100)
lunch = st.number_input("Lunch Calories", min_value=0, step=100)
dinner = st.number_input("Dinner Calories", min_value=0, step=100)
exercise = st.number_input("Exercise Calories Burned", min_value=0, step=100)

# Database Connection
conn = get_db_connection()

if conn:
    # Create tables if they don't exist
    create_tables(conn)

    if st.button("Save Data"):
        insert_calorie_data(conn, breakfast, lunch, dinner, exercise, intake_date)

    # Data Retrieval and Visualization
    st.subheader("Calorie Progress")

    # Date range selection
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_last_week = start_of_week - timedelta(days=7)

    view_option = st.selectbox("Select Time Range", ["Today", "This Week", "Last Week", "All Time"])

    if view_option == "Today":
        start_date = today
        end_date = today
    elif view_option == "This Week":
        start_date = start_of_week
        end_date = today
    elif view_option == "Last Week":
        start_date = start_of_last_week
        end_date = start_of_week - timedelta(days=1)
    else:  # All Time
        start_date = date(2000, 1, 1)  # A date far in the past
        end_date = today

    df = get_calorie_data(conn, start_date, end_date)

    if not df.empty:
        df['Net Calories'] = df['breakfast'] + df['lunch'] + df['dinner'] - df['exercise']
        df['date'] = pd.to_datetime(df['date']).dt.date

        st.write("DataFrame Contents:")  # Add this for debugging
        st.write(df)                    # Add this for debugging
        st.dataframe(df)


        fig = px.line(df, x='date', y='Net Calories', title='Net Calorie Intake Over Time')
        fig.update_xaxes(title_text='Date', tickformat="%Y-%m-%d")  # Add this line
        fig.update_yaxes(title_text='Net Calories', range=[0, df['Net Calories'].max() * 1.1]) # Add this
        st.plotly_chart(fig)

    else:
        st.write("No data available for the selected period.")

    conn.close()
else:
    st.error("Could not connect to the database.  Check your connection settings.")