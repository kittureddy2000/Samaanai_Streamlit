# db.py (Modified get_calorie_data and get_all_data_for_date)
import psycopg2
from sqlalchemy import create_engine, text
import os
import pandas as pd
import logging
from sqlalchemy.exc import SQLAlchemyError
import streamlit as st


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

db_user = os.environ.get("DB_USER", "postgres")
db_pass = os.environ.get("DB_PASSWORD", "password")
db_name = os.environ.get("DB_NAME", "samaan_db")
db_host = os.environ.get("DB_HOST", "localhost")
db_port = os.environ.get("DB_PORT", "5432")

def get_db_connection():
    """Creates a database connection."""
    try:
        if db_host.startswith("/cloudsql/"):
            engine = create_engine(f"postgresql+psycopg2://{db_user}:{db_pass}@/{db_name}?host={db_host}")
        else:
            engine = create_engine(f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}")
        conn = engine.connect()
        logger.info("Database connection successful!")
        return conn
    except Exception as e:
        logger.error(f"CRITICAL ERROR: Could not connect to the database: {e}")
        return None

def create_calorie_counter_tables(conn):
    """Creates the necessary tables, including a unique constraint."""
    try:
        with conn.execution_options(isolation_level="AUTOCOMMIT").begin() as trans:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS health_calorie_intake (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL UNIQUE,
                    exercise INT,
                    weight NUMERIC NOT NULL
                );
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS health_meal_details (
                    id SERIAL PRIMARY KEY,
                    calorie_intake_id INTEGER REFERENCES health_calorie_intake(id) ON DELETE CASCADE,
                    meal_type VARCHAR(255) NOT NULL,
                    calories INT,
                    protein INT,
                    fiber INT,
                    carbs INT,
                    UNIQUE(calorie_intake_id, meal_type)  -- ADD THIS UNIQUE CONSTRAINT
                );
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS health_weight_loss_goal (
                    id SERIAL PRIMARY KEY,
                    goal_lbs_per_week NUMERIC NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE,
                    rmr INT NOT NULL,
                    UNIQUE(start_date, end_date)
                );
            """))
        logger.info("Tables created successfully!")

    except Exception as e:
        logger.exception(f"Error creating tables: {e}")

def insert_calorie_data(conn, intake_date, exercise, weight):
    """Inserts calorie data (date, exercise, and weight), handling transactions."""
    logger.info(f"Inserting calorie data for date: {intake_date}, exercise: {exercise}, weight: {weight}")
    try:
        with conn.begin() as trans:
            result = conn.execute(
                text("""
                INSERT INTO health_calorie_intake (date, exercise, weight)
                VALUES (:date, :exercise, :weight)
                ON CONFLICT (date) DO UPDATE
                SET exercise = EXCLUDED.exercise,
                    weight = EXCLUDED.weight
                RETURNING id;
                """),
                {"date": intake_date, "exercise": exercise, "weight": weight}
            )
            row = result.fetchone()
            if row:
                trans.commit()
                logger.info(f"insert_calorie_data successful. ID: {row[0]}")
                return row[0]
            else:
                trans.rollback()
                logger.error("Error: insert_calorie_data - No ID returned.")
                return None
    except SQLAlchemyError as e:
        logger.error(f"Error in insert_calorie_data: {e}")
        trans.rollback()
        return None

def insert_meal_details(conn, calorie_intake_id, meal_type, calories, protein, fiber, carbs):
    """Inserts or updates meal details, handling transactions and conflicts."""
    logger.info(f"Inserting/Updating meal details for intake ID: {calorie_intake_id}, meal_type: {meal_type}")
    try:
        with conn.begin() as trans:
            conn.execute(
                text("""
                INSERT INTO health_meal_details (calorie_intake_id, meal_type, calories, protein, fiber, carbs)
                VALUES (:calorie_intake_id, :meal_type, :calories, :protein, :fiber, :carbs)
                ON CONFLICT (calorie_intake_id, meal_type) DO UPDATE
                SET calories = EXCLUDED.calories,
                    protein = EXCLUDED.protein,  -- Update all relevant fields
                    fiber = EXCLUDED.fiber,
                    carbs = EXCLUDED.carbs;
                """),
                {
                    "calorie_intake_id": calorie_intake_id,
                    "meal_type": meal_type,
                    "calories": calories,
                    "protein": protein,
                    "fiber": fiber,
                    "carbs": carbs,
                }
            )
            trans.commit()
            logger.info(f"insert_meal_details successful. intake_id: {calorie_intake_id}, meal_type: {meal_type}")
    except Exception as e:
        logger.exception(f"Error in insert_meal_details: {e}")
        trans.rollback()


def insert_weight_loss_goal(conn, goal_lbs_per_week, start_date, rmr_value, end_date=None):
    """Inserts or updates the weight loss goal."""
    logger.info(f"Inserting/updating weight loss goal: goal_lbs_per_week={goal_lbs_per_week}, start_date={start_date}, rmr={rmr_value}, end_date={end_date}")
    try:
        with conn.begin() as trans:
            if end_date:
                conn.execute(
                    text("""
                        INSERT INTO health_weight_loss_goal (goal_lbs_per_week, start_date, end_date, rmr)
                        VALUES (:goal_lbs_per_week, :start_date, :end_date, :rmr)
                        ON CONFLICT (start_date, end_date) DO UPDATE
                        SET goal_lbs_per_week = EXCLUDED.goal_lbs_per_week,
                            rmr = EXCLUDED.rmr;
                    """),
                    {"goal_lbs_per_week": goal_lbs_per_week, "start_date": start_date, "end_date": end_date, "rmr": rmr_value}
                )
            else:
                conn.execute(
                    text("""
                        INSERT INTO health_weight_loss_goal (goal_lbs_per_week, start_date, end_date, rmr)
                        VALUES (:goal_lbs_per_week, :start_date, NULL, :rmr)
                        ON CONFLICT (start_date, end_date) DO UPDATE
                        SET goal_lbs_per_week = EXCLUDED.goal_lbs_per_week,
                            rmr = EXCLUDED.rmr;
                    """),
                    {"goal_lbs_per_week": goal_lbs_per_week, "start_date": start_date, "rmr": rmr_value}
                )
            trans.commit()
            logger.info(f"insert_weight_loss_goal successful.")
    except Exception as e:
        logger.exception(f"Error inserting weight loss goal: {e}")
        trans.rollback()

def get_calorie_data(conn, start_date, end_date):
    """Retrieves calorie data for the summary table."""
    logger.info(f"Retrieving calorie data for dates between {start_date} and {end_date}")
    try:
        query = text("""
            SELECT
                ci.date,
                SUM(CASE WHEN md.meal_type = 'breakfast' THEN md.calories ELSE 0 END) as breakfast_calories,
                SUM(CASE WHEN md.meal_type = 'lunch' THEN md.calories ELSE 0 END) as lunch_calories,
                SUM(CASE WHEN md.meal_type = 'dinner' THEN md.calories ELSE 0 END) as dinner_calories,
                SUM(CASE WHEN md.meal_type = 'snacks' THEN md.calories ELSE 0 END) as snacks_calories,
                ci.exercise as exercise_calories
            FROM health_calorie_intake ci
            LEFT JOIN health_meal_details md ON ci.id = md.calorie_intake_id
            WHERE ci.date >= :start_date AND ci.date <= :end_date
            GROUP BY ci.date, ci.exercise
            ORDER BY ci.date;
        """)
        df = pd.read_sql_query(query, conn, params={"start_date": start_date, "end_date": end_date})

        if not df.empty:
            df['Total Sum'] = df['breakfast_calories'] + df['lunch_calories'] + df['dinner_calories'] + df['snacks_calories'] - df['exercise_calories']

        logger.info(f"get_calorie_data successful. Rows returned: {len(df)}")
        return df
    except Exception as e:
        logger.exception(f"Error retrieving calorie data: {e}")
        return pd.DataFrame()

def get_current_weight_loss_goal(conn):
    """Retrieves the current weight loss goal (including RMR)."""
    logger.info("Retrieving current weight loss goal...")
    try:
        query = text("""
            SELECT goal_lbs_per_week, start_date, end_date, rmr
            FROM health_weight_loss_goal
            WHERE end_date IS NULL
            ORDER BY start_date DESC
            LIMIT 1;
        """)
        result = conn.execute(query).fetchone()
        if result:
            logger.info(f"get_current_weight_loss_goal successful. Goal: {result[0]}")
            return result
        logger.info("get_current_weight_loss_goal: No current goal found.")
        return None, None, None, None  # No current goal
    except Exception as e:
        logger.exception(f"Error retrieving current weight loss goal: {e}")
        return None, None, None, None

def get_weight_loss_goal_by_date(conn, target_date):
    """Retrieves the weight loss goal (including RMR) for a specific date."""
    logger.info(f"Retrieving weight loss goal for date: {target_date}")
    try:
        query = text("""
            SELECT goal_lbs_per_week, rmr
            FROM health_weight_loss_goal
            WHERE start_date <= :target_date AND (end_date >= :target_date OR end_date IS NULL)
            ORDER BY start_date DESC
            LIMIT 1;
        """)
        result = conn.execute(query, {"target_date": target_date}).fetchone()
        if result:
            logger.info(f"get_weight_loss_goal_by_date successful. Goal: {result[0]}")
            return result
        logger.info(f"get_weight_loss_goal_by_date: No goal found for date {target_date}")
        return None, None
    except Exception as e:
        logger.exception(f"Error retrieving weight loss goal by date: {e}")
        return None, None

def get_all_data_for_date(conn, target_date):
    """Retrieves all data for a given date, joining across tables, including snacks."""
    logger.info(f"Retrieving all data for date: {target_date}")
    try:
        query = text("""
            SELECT
                ci.exercise,
                ci.weight,
                md.meal_type,
                md.calories,
                wlg.rmr,
                wlg.goal_lbs_per_week
            FROM health_calorie_intake ci
            LEFT JOIN health_meal_details md ON ci.id = md.calorie_intake_id
            LEFT JOIN health_weight_loss_goal wlg ON ci.date >= wlg.start_date
                                            AND (ci.date <= wlg.end_date OR wlg.end_date IS NULL)
            WHERE ci.date = :target_date;
        """)
        result = pd.read_sql_query(query, conn, params={"target_date": target_date})
        logger.debug(f"Raw result from get_all_data_for_date: {result}")

        if not result.empty:
            # Pivot directly, since we only care about calories now.
            result = result.pivot_table(index=['exercise', 'weight', 'rmr', 'goal_lbs_per_week'],
                                        columns=['meal_type'],
                                        values='calories',
                                        fill_value=0,
                                        dropna=False).reset_index()

            # Ensure 'snacks' column exists
            if 'snacks' not in result.columns:
                result['snacks'] = 0

            result.columns = [col[0] if isinstance(col, str) else col for col in result.columns] #remove tuple
            logger.debug(f"Final result columns: {result.columns}")

        logger.info(f"get_all_data_for_date successful. Rows returned: {len(result)}")
        return result
    except Exception as e:
        logger.exception(f"Error retrieving all data for date: {e}")
        return pd.DataFrame()
    
def create_stock_table(conn):
    """Creates the stocks table if it doesn't exist."""
    try:
        with conn.begin() as trans:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS stocks (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    symbol VARCHAR(10) NOT NULL,
                    name VARCHAR(100),
                    quantity INTEGER NOT NULL,
                    date_purchased DATE,
                    date_sold DATE,
                    purchase_price NUMERIC(10, 2) NOT NULL,
                    sold_price NUMERIC(10, 2),
                    source VARCHAR(100),
                    comments TEXT,
                    UNIQUE(user_id, symbol)
                );
            """))
        logger.info("Stocks table created/exists.")
    except Exception as e:
        logger.exception(f"Error creating stocks table: {e}")
        st.error(f"Error creating database table: {e}") # Show error to user.
        st.stop() # Stop execution
