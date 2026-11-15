current_year = date.today().year
min_date = date(current_year - 100, 1, 1)
max_date = date(current_year + 100, 12, 31)
selected_date = st.date_input("తేదీ (Date)", value=date.today(), min_value=min_date, max_value=max_date)