import pandas as pd
import numpy as np
import re
import streamlit as st
import pyperclip
import os
# Streamlit setup
st.title("Medication Reconciliation Tool")
st.write("Enter or paste the text input below and ensure the 'medication list.xlsx' file is in the same directory as this script.")

# Initialize session state for the output text
if 'output_text' not in st.session_state:
    st.session_state.output_text = ""

# User input
user_input = st.text_area("Enter or paste the text input here:")

# File path for medication list
med_list_file_path = 'medication list.xlsx'

# Add an "Analyze" button
if st.button("Analyze"):
    if user_input and os.path.exists(med_list_file_path):
        # Read the medication list file
        med_list_df = pd.read_excel(med_list_file_path)
        medication = med_list_df['Order Name'].tolist()
        
        # Process user input
        input_lines = user_input.split('\n')
        data_range = [line.split('\t') for line in input_lines if line.strip()]

        # Convert to DataFrame
        data_range_df = pd.DataFrame(data_range)

        cell_location = data_range_df[data_range_df == 'Additional Current Orders'].stack().index.tolist()

        if not cell_location:
            st.error("Additional Current Orders not found")
        else:
            row_idx, col_idx = cell_location[0]

            additional_orders = pd.DataFrame(data_range_df.values[row_idx+1:], columns=data_range_df.iloc[row_idx])
            additional_orders = additional_orders[['Additional Current Orders']]

            end_row = row_idx - 2

            if end_row < 0:
                st.error("Not enough rows to skip two rows before Additional Current Orders")
            else:
                df = pd.DataFrame(data_range_df.values[:row_idx-2])

                def remove_rows_before_string(df, target_string):
                    loc = None
                    for i, row in df.iterrows():
                        if target_string in row.values:
                            loc = i
                            break
                    if loc is None:
                        st.write(f"{target_string} not found in dataframe.")
                        return df
                    return df.iloc[loc:].reset_index(drop=True)

                df = remove_rows_before_string(df, 'Admission PML')
                df.columns = df.iloc[0]
                df = df.drop(df.index[0]).reset_index(drop=True)
                df = df[['Admission PML', 'Reconciled with current Order']]

                df = df.replace('NEHR Medication ', '', regex=True)
                df = df.replace('Other Medication ', '', regex=True)
                additional_orders = additional_orders.replace('NEHR Medication ', '', regex=True)
                additional_orders = additional_orders.replace('Other Medication ', '', regex=True)

                df['Admission PML'] = df['Admission PML'].str.strip()
                df['Reconciled with current Order'] = df['Reconciled with current Order'].str.strip()
                additional_orders['Additional Current Orders'] = additional_orders['Additional Current Orders'].str.strip()

                df = df.replace(' ', None)
                df = df.replace('', None)

                def modify_values(value):
                    if pd.isna(value):
                        return value
                    modified_text = re.sub(r'(weeks|week|days|day)([a-zA-Z0-9])', r'\1 \2', value)
                    return modified_text

                df = df.applymap(modify_values)
                additional_orders = additional_orders.applymap(modify_values)

                admission_orders = df[['Admission PML']]
                current_orders = pd.DataFrame({'Current Orders': pd.concat([df['Reconciled with current Order'], additional_orders['Additional Current Orders']], ignore_index=True)})
                current_orders = current_orders[current_orders['Current Orders'].notnull()]

                def find_substring(row, col, substring_list):
                    row_value = row[col]
                    if pd.isna(row_value):
                        return None
                    for substring in substring_list:
                        if pd.isna(substring):
                            continue
                        if substring.lower() in row_value.lower():
                            start_index = row_value.lower().index(substring.lower())
                            end_index = start_index + len(substring.lower())
                            return row_value[start_index:end_index]
                    return None

                def find_text_after(row, col1, col2):
                    col1_value = row[col1]
                    col2_value = row[col2]
                    if pd.isnull(col1_value) or pd.isnull(col2_value):
                        return None
                    index = col1_value.find(col2_value)
                    if index != -1:
                        return col1_value[index + len(col2_value) + 1:]
                    else:
                        return None

                admission_orders['Admission Medication'] = admission_orders.apply(find_substring, axis=1, col='Admission PML', substring_list=medication)
                admission_orders['Admission Route/Dose/Frequency'] = admission_orders.apply(find_text_after, axis=1, col1='Admission PML', col2='Admission Medication')

                current_orders['Current Medication'] = current_orders.apply(find_substring, axis=1, col='Current Orders', substring_list=medication)
                current_orders['Current Route/Dose/Frequency'] = current_orders.apply(find_text_after, axis=1, col1='Current Orders', col2='Current Medication')

                def check_substring_in_df(row_value, df, col_name):
                    if pd.isnull(row_value):
                        return False
                    pattern = re.compile(re.escape(row_value), re.IGNORECASE)
                    return any(pattern.search(str(string)) for string in df[col_name] if not pd.isnull(string))

                def check_substring_in_other_df(row, col1, col2, df2):
                    row_value = row[col1]
                    if pd.isna(row_value):
                        return False
                    elements = row_value.split(' ')
                    other_col_values = df2[col2].str.lower()
                    num_elements = [element for element in elements if element.isdigit()]
                    non_num_elements = [element for element in elements if not element.isdigit()]
                    for value in other_col_values:
                        if pd.isna(value):
                            continue
                        if all(element.lower() in value for element in non_num_elements):
                            non_num_row = value
                            if len(num_elements) == 0:
                                return True
                            if all(element in non_num_row.split(' ') for element in num_elements):
                                return True
                    return False

                def check_substring_in_other_df_swapped(row, col1, col2, df2):
                    row_value = row[col1]
                    if pd.isna(row_value):
                        return False
                    other_col_values = df2[col2].str.lower()
                    for value in other_col_values:
                        if pd.isna(value):
                            continue
                        elements = value.split(' ')
                        num_elements = [element for element in elements if element.isdigit()]
                        non_num_elements = [element for element in elements if not element.isdigit()]
                        if all(element in row_value.lower() for element in non_num_elements):
                            non_num_row = row_value.lower()
                            if len(num_elements) == 0:
                                return True
                            if all(element in non_num_row.split(' ') for element in num_elements):
                                return True
                    return False

                def match_admission_orders(row):
                    if check_substring_in_other_df(row, col1='Admission PML', col2='Current Orders', df2=current_orders):
                        return 'OK'
                    elif check_substring_in_other_df_swapped(row, col1='Admission PML', col2='Current Orders', df2=current_orders):
                        return 'OK'
                    elif check_substring_in_df(row['Admission Medication'], current_orders, 'Current Medication'):
                        return 'Changes'
                    else:
                        return 'Omission'

                admission_orders['Category'] = admission_orders.apply(match_admission_orders, axis=1)

                def match_current_orders(row):
                    if check_substring_in_other_df(row, col1='Current Orders', col2='Admission PML', df2=admission_orders):
                        return 'OK'
                    elif check_substring_in_other_df_swapped(row, col1='Current Orders', col2='Admission PML', df2=admission_orders):
                        return 'OK'
                    elif check_substring_in_df(row['Current Medication'], admission_orders, 'Admission Medication'):
                        if (admission_orders[admission_orders['Admission Medication'] == row['Current Medication']]['Category'] == 'OK').any():
                            if (admission_orders[admission_orders['Admission Medication'] == row['Current Medication']]['Category'] == 'Changes').any():
                                return 'Changes'
                            else:
                                return 'Addition'
                        else:
                            return 'Changes'
                    else:
                        return 'Addition'

                current_orders['Category'] = current_orders.apply(match_current_orders, axis=1)

                # Prepare output
                output = []
                
                # Omission
                output.append("**1. Omission**\nPatient was on the following medications prior to admission, but not ordered in ward:")
                omissions = admission_orders[admission_orders['Category'] == 'Omission']['Admission PML'].tolist()
                for medication in omissions:
                    output.append(f"{medication}")
                
                # Addition
                output.append("\n**2. Addition**\nPatient was not on the following medications prior to admission:")
                additions = current_orders[current_orders['Category'] == 'Addition']['Current Orders'].tolist()
                for medication in additions:
                    output.append(f"{medication}")
                
                # Change in dose/frequency
                output.append("\n**3. Change in dose / frequency**\nThese medicines were ordered with different dose / frequency:")
                changes = admission_orders[admission_orders['Category'] == 'Changes'][['Admission PML', 'Admission Medication', 'Admission Route/Dose/Frequency']]
                changes = changes.merge(current_orders[current_orders['Category']=='Changes'][['Current Medication', 'Current Route/Dose/Frequency']], left_on='Admission Medication', right_on='Current Medication', how='left')
                changes['Change'] = changes['Admission Medication'].astype(str) + " [" + changes['Admission Route/Dose/Frequency'].astype(str) + "] to [" + changes['Current Route/Dose/Frequency'].astype(str) + "]"
                changes_list = changes['Change'].tolist()
                for i in range(len(changes)):
                    admission_details = changes.loc[i, 'Admission PML']
                    current_details = changes.loc[i, 'Current Route/Dose/Frequency']
                    output.append(f"Patient was on [{admission_details}], but ordered [{current_details}] in ward")
                
                # Store output text in session state before displaying
                st.session_state.output_text = '\n'.join(output)

                # Display output in Streamlit
                st.markdown("**<span style='color:blue'>Medication Reconciliation Output:</span>**", unsafe_allow_html=True)
                st.text_area("", value=st.session_state.output_text, height=300)
                
                # Add a button to copy output to clipboard
                if st.button("Copy to Clipboard"):
                    pyperclip.copy(st.session_state.output_text)
                    st.success("Output copied to clipboard!")

                # Store output as dataframe
                omission_data = [(med, 'Omission') for med in omissions]
                addition_data = [(med, 'Addition') for med in additions]
                change_data = [(med, 'Change in dose / frequency') for med in changes_list]

                output_data = omission_data + addition_data + change_data
                df_output = pd.DataFrame(output_data, columns=['Medication', 'Category'])

                # Function to color-code the DataFrame
                def color_code(val):
                    if val == 'Omission':
                        color = 'red'
                    elif val == 'Addition':
                        color = 'green'
                    elif val == 'Change in dose / frequency':
                        color = 'orange'
                    else:
                        color = 'black'
                    return f'color: {color}'

                # Apply the color-code function
                styled_df_output = df_output.style.applymap(color_code, subset=['Category'])

                # Display output in Streamlit
                st.markdown("**<span style='color:blue'>Output DataFrame:</span>**", unsafe_allow_html=True)
                st.write(styled_df_output.to_html(escape=False), unsafe_allow_html=True)

                # Add download button for the DataFrame
                csv = df_output.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name='medication_reconciliation.csv',
                    mime='text/csv',
                )
    else:
        st.warning("Please enter or paste the text input and ensure the 'medication list.xlsx' file is in the same directory as this script to proceed.")
