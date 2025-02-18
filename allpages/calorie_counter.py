# allpages/calorie_counter.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from db import (get_db_connection, insert_calorie_data,
                get_calorie_data, insert_weight_loss_goal,
                get_current_weight_loss_goal,
                get_all_data_for_date, insert_meal_details,
                create_calorie_counter_tables)
from allpages.utils import get_thursday_to_wednesday_range  # Make SURE this is correct
import logging
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def calorie_counter_page(conn):
    st.title("Calorie Counter")

    create_calorie_counter_tables(conn)

    intake_date = st.date_input("Date", date.today())
    logger.info(f"Selected date: {intake_date}")

    conn = get_db_connection()
    if not conn:
        st.error("Could not connect to the database.")
        return

    existing_data = get_all_data_for_date(conn, intake_date)
    logger.debug(f"Existing data: {existing_data}")

    # --- Input Section (All in one row) ---
    st.subheader("Daily Data")
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        weight_value = st.number_input("Weight (lbs)", min_value=0.0, step=0.1,
                                        value=(float(existing_data.get('weight', pd.Series(150.0)).iloc[0]) if not existing_data.empty else 150.0))
    with col2:
        exercise = st.number_input("Exercise Calories", min_value=0, step=100,
                                    value=int(existing_data.get('exercise', pd.Series(0)).iloc[0]) if not existing_data.empty else 0)
    with col3:
        breakfast_calories = st.number_input("Breakfast Calories", min_value=0, step=100,
                                            value=int(existing_data.get('breakfast', pd.Series(0)).iloc[0]) if not existing_data.empty else 0,
                                             key="breakfast_calories")
    with col4:
        lunch_calories = st.number_input("Lunch Calories", min_value=0, step=100,
                                          value=int(existing_data.get('lunch', pd.Series(0)).iloc[0]) if not existing_data.empty else 0,
                                          key="lunch_calories")
    with col5:
        dinner_calories = st.number_input("Dinner Calories", min_value=0, step=100,
                                           value=int(existing_data.get('dinner', pd.Series(0)).iloc[0]) if not existing_data.empty else 0,
                                           key="dinner_calories")
    with col6:
        snacks_calories = st.number_input("Snacks Calories", min_value=0, step=100,
                                           value=int(existing_data.get('snacks', pd.Series(0)).iloc[0]) if not existing_data.empty else 0,  # Handle potential missing 'snacks'
                                           key="snacks_calories")


    if st.button("Save Daily Data"):
        conn = get_db_connection()
        if not conn:
            st.error("Could not connect to the database.")
            return
        logger.info(f"Save Daily Data button clicked.  Inserting/updating data for date: {intake_date}")
        try:
            calorie_intake_id = insert_calorie_data(conn, intake_date, exercise, weight_value)
            logger.info(f"Returned calorie_intake_id: {calorie_intake_id}")

            if calorie_intake_id:
                logger.info("Inserting meal details...")
                insert_meal_details(conn, calorie_intake_id, "breakfast", breakfast_calories, 0, 0, 0)
                insert_meal_details(conn, calorie_intake_id, "lunch", lunch_calories, 0, 0, 0)
                insert_meal_details(conn, calorie_intake_id, "dinner", dinner_calories, 0, 0, 0)
                insert_meal_details(conn, calorie_intake_id, "snacks", snacks_calories, 0, 0, 0)  # Add snacks
                st.success("All data saved successfully!")
            else:
                st.error("Failed to save calorie intake data.")
        except SQLAlchemyError as e:
            logger.exception(f"Error while saving daily data: {e}")
            st.error(f"A database error occurred: {e}")
        finally:
            if conn:
                conn.close()

    with st.expander("Set Weight Loss Goal"):
        goal_lbs_per_week = st.number_input("Goal (lbs/week)", min_value=0.0, max_value=5.0, step=0.1, value=2.0)
        goal_start_date = st.date_input("Goal Start Date", date.today())
        rmr_value = st.number_input("Resting Metabolic Rate (RMR)", min_value=0, step=10, value=1843)
        if st.button("Set Goal"):
            conn = get_db_connection()
            if not conn:
                st.error("Could not connect to the database")
                return
            logger.info(f"Setting weight loss goal: {goal_lbs_per_week} lbs/week, RMR: {rmr_value}, Start Date: {goal_start_date}")
            try:
                insert_weight_loss_goal(conn, goal_lbs_per_week, goal_start_date, rmr_value)
                st.success("Goal Data inserted successfully!")
            except SQLAlchemyError as e:
                logger.exception(f"Error while saving goal data: {e}")
                st.error(f"A database error occurred: {e}")
            finally:
                if conn:
                    conn.close()

    st.subheader("Calorie Progress")

    today = date.today()
    this_week_start, this_week_end = get_thursday_to_wednesday_range(today)
    last_week_start, last_week_end = get_thursday_to_wednesday_range(today - timedelta(days=7))

    view_option = st.selectbox("Select Time Range", ["Today", "This Week", "Last Week", "All Time"])

    if view_option == "Today":
        start_date = today
        end_date = today
    elif view_option == "This Week":
        start_date = this_week_start
        end_date = this_week_end
    elif view_option == "Last Week":
        start_date = last_week_start
        end_date = last_week_end
    else:
        start_date = date(2000, 1, 1)
        end_date = today

    df = get_calorie_data(conn, start_date, end_date)
    conn.close()
    logger.info(f"Retrieved data for plotting: {df}")


    # --- Summarized Table ---
    st.subheader("Daily Calorie Summary")
    if not df.empty:
        st.dataframe(df)  # Display the summarized DataFrame
    else:
        st.write("No data available for the selected period.")


    # --- Combined Graph ---
    if not df.empty:
        conn = get_db_connection()
        if not conn:
            st.error("Could not connect to the database.")
            return
        current_goal_data = get_current_weight_loss_goal(conn)
        conn.close()

        if current_goal_data:
            current_goal, goal_start, _, current_rmr = current_goal_data
            current_goal = float(current_goal) if current_goal is not None else 0.0
            current_rmr = float(current_rmr) if current_rmr is not None else 1843.0
        else:
            current_goal, current_rmr, goal_start = 0.0, 1843.0, None

        df['Target Calories'] = current_rmr - (current_goal * 500)

        # Prepare data for combined graph
        df_melted = pd.melt(df, id_vars=['date'], value_vars=['Total Sum', 'Target Calories'],
                            var_name='Type', value_name='Calories')

        fig = px.line(df_melted, x='date', y='Calories', color='Type',
                      title='Total Calories vs. Target Calories',
                      color_discrete_map={"Total Sum": "blue", "Target Calories": "red"})
        fig.update_xaxes(title_text='Date', tickformat="%Y-%m-%d")
        fig.update_yaxes(title_text='Calories')
        st.plotly_chart(fig)


        # --- Goal Summary (Corrected Calculation) ---
        st.subheader("Goal Summary")
        if current_goal_data:
            st.write(f"Current Weight Loss Goal: {current_goal} lbs/week")
            st.write(f"Current Resting Metabolic Rate: {current_rmr} calories")
            if goal_start:
                st.write(f"Goal Start Date: {goal_start.strftime('%Y-%m-%d')}")

            weekly_target_calories = (current_rmr - (current_goal * 500)) * 7
            #total_calories = df['Total Sum'].sum() #  sum of the 'Total Sum' column
            total_calories = df['Total Sum'].sum()

            st.write(f"Weekly Target Calories: {weekly_target_calories:.2f}")
            st.write(f"Total Net Calories This Period: {total_calories:.2f}")

            if total_calories > weekly_target_calories:
                st.write(f"You are {(total_calories - weekly_target_calories):.2f} calories above your target.")
            else:
                st.write(f"You are {(weekly_target_calories - total_calories):.2f} calories below your target.")
        else:
            st.write("No weight loss goal set.")