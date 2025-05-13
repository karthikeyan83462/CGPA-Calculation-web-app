from flask import Flask, render_template, request, redirect, url_for
import pdfplumber

import pandas as pd
import unicodedata
import re
from io import BytesIO

app = Flask(__name__)


def clean_text(text):
    if isinstance(text, str):
        # Normalize Unicode characters (e.g., replace "" with real characters if possible)
        text = unicodedata.normalize("NFKD", text)
        # Replace non-ASCII characters with empty string (or use ASCII fallback)
        text = text.encode("ascii", "ignore").decode("ascii")
        # Replace multiple spaces/newlines/tabs with single space
        return re.sub(r'\s+', ' ', text).strip()
    return text


def extract_table_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        first_page = pdf.pages[0]
        table = first_page.extract_table()

        if table:
            df = pd.DataFrame(table[1:], columns=table[0])
            df.columns = [col.strip() for col in df.columns]

            # Rename to expected column names
            df.rename(columns={
                'Course Name': 'Subject',
                'Credits': 'Credit',
                'Grade Point': 'Grade',
            }, inplace=True)

            # Clean text for all relevant columns
            for col in ['Subject', 'Grade', 'Credit']:
                if col in df.columns:
                    df[col] = df[col].apply(clean_text)

            # Remove rows with missing/empty Grade or Credit
            df = df[df['Grade'].str.strip().astype(bool)]  # Keep only non-empty grades
            df = df[df['Credit'].str.strip().astype(bool)]  # Keep only non-empty credits

            print("Normalized Columns:", df.columns)
            return df
    return None




# Function to calculate GPA from DataFrame
def calculate_gpa(df):
    grade_map = {
        "O": 10,
        "A+": 9,
        "A": 8,
        "B+": 7,
        "B": 6,
        "RA": 0,  # Reappear/Fail
    }

    total_credits = 0
    total_points = 0

    for index, row in df.iterrows():
        grade = str(row.get('Grade', '')).strip().upper()
        try:
            credit = float(row.get('Credit', 0))  # Convert to float
        except ValueError:
            continue  # Skip rows where credit is not a number

        if grade in grade_map:
            grade_point = grade_map[grade]
            total_credits += credit
            total_points += grade_point * credit

    gpa = total_points / total_credits if total_credits > 0 else 0
    return round(gpa, 2)


# Home route - Welcome page asking user choice
@app.route('/')
def index():
    return render_template('index.html')

# Manual entry route
@app.route('/manual', methods=['GET', 'POST'])
def manual_entry():
    if request.method == 'POST':
        semester_numbers = request.form.getlist('semester[]')
        all_semesters_data = []
        total_credits = 0
        total_points = 0

        for sem in semester_numbers:
            subjects = request.form.getlist(f'subject_{sem}[]')
            grades = request.form.getlist(f'grade_{sem}[]')
            credits = request.form.getlist(f'credit_{sem}[]')

            data = {
                'Subject': subjects,
                'Grade': grades,
                'Credit': credits
            }
            df = pd.DataFrame(data)
            gpa = calculate_gpa(df)

            all_semesters_data.append({
                'semester': sem,
                'subjects': df.to_dict(orient='records'),
                'gpa': gpa
            })

            # For CGPA
            grade_map = {
                "O": 10,
                "A+": 9,
                "A": 8,
                "B+": 7,
                "B": 6,
                "RA": 0,
            }
            for i in range(len(subjects)):
                grade = grades[i].strip().upper()
                try:
                    credit = float(credits[i])
                except ValueError:
                    continue
                if grade in grade_map:
                    point = grade_map[grade]
                    total_credits += credit
                    total_points += point * credit

        cgpa = round(total_points / total_credits, 2) if total_credits > 0 else 0

        return render_template('manual_result.html', results=all_semesters_data, cgpa=cgpa)

    return render_template('manual_entry.html')



@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'files' not in request.files:
            return 'No files part'
        
        files = request.files.getlist('files')
        all_data = []
        total_credits = 0
        total_points = 0

        for file in files:
            if file and file.filename.endswith('.pdf'):
                pdf_data = BytesIO(file.read())
                df = extract_table_from_pdf(pdf_data)
                
                if df is not None:
                    print(f"Extracted Data for {file.filename}:")
                    print(df.head())  # Debugging extracted data
                    gpa = calculate_gpa(df)
                    all_data.append((file.filename, df, gpa))
                    
                    # Calculate CGPA
                    grade_map = {
                        "O": 10,
                        "A+": 9,
                        "A": 8,
                        "B+": 7,
                        "B": 6,
                        "RA": 0
                    }
                    for index, row in df.iterrows():
                        grade = str(row.get('Grade', '')).strip().upper()
                        try:
                            credit = float(row.get('Credit', 0))
                        except ValueError:
                            continue
                        if grade in grade_map:
                            point = grade_map[grade]
                            total_credits += credit
                            total_points += point * credit
                else:
                    return f"No table found in file {file.filename}"
            else:
                return 'Invalid file(s). Please upload PDFs only.'

        cgpa = round(total_points / total_credits, 2) if total_credits > 0 else 0
        return render_template('cgpa_result.html', results=all_data, cgpa=cgpa)

    return render_template('upload_page.html')




if __name__ == '__main__':
    app.run(debug=True)
