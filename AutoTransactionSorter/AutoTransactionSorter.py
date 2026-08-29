import pdfplumber
import sqlite3
import pandas as pd
import os
from database import Database
from classifier import NULL, Classifier
import plotly.express as px

db = Database()
cl = Classifier()

#Get the path of each file in the import folder
folder = "<SECRET>";
fileList = []
for file in os.listdir(folder):
    if file.endswith(".pdf"):
        fileList.append(os.path.join(folder, file))

def extractTransactionsFromPDF(file):
    with pdfplumber.open(file) as pdf:
        rows = []
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                rows.extend(table)
        # Should have 6 column in each row. Remove the ones that don't have 6 columns. And remove the last column of each row
        rows = [row[:-1] for row in rows if len(row) == 6]
        # When a row have no date, append text to the previous row then remove it from the list
        i = 2
        while i < len(rows):
            if len(rows[i]) > 0 and rows[i][0] == '':
                # Append the text to the previous row
                rows[i - 1][2] += ' ' + rows[i][2]
                # Remove the current row
                rows.pop(i)
            else:
                i += 1

        # Add a new column to the rows to store the category of each transaction. The category will be determined later based on the libelle of the transaction.
        rows = [row + [None] for row in rows]
        return rows

def storeMonthlyBalanceInDatabase(rows):
    #Store monthly balance in the database
    monthlyBalanceDebit = -float(rows[1][3]) if rows[1][3] != '' else 0.0
    monthlyBalanceCredit = float(rows[1][4]) if rows[1][4] != '' else 0.0
    monthlyBalance = monthlyBalanceDebit + monthlyBalanceCredit
    #extract balance date from the first row libelle of format : "Ancien solde créditeur au 18.05.2026"
    date = rows[1][2].split("au")[-1].strip()
    db.upsert_monthly_balance(date, monthlyBalance)

def storeTransactionsInDatabase(df):
    db.upsert_transaction(df)

for file in fileList:
    #Extract from PDF
    rows = extractTransactionsFromPDF(file)

    # Filter rows where neither debit or credit can be parsed to float. This will remove rows that are not transactions, such as the header and footer of the PDF.
    transactionRows = []
    for row in rows:
        try:
            debit = float(row[3].replace(',', '.').replace(' ', '')) if row[3] != '' else 0.0
            credit = float(row[4].replace(',', '.').replace(' ', '')) if row[4] != '' else 0.0
            row[3] = debit
            row[4] = credit
            # Check if date is not null or empty
            if row[0] is not None and row[0] != '':
                transactionRows.append(row)
        except ValueError:
            pass

    # Create a structured pandas dataframe to store operations. Parse the debit and credit columns to float and set the categorie column to None. The dataframe will have the following columns: date_operation, date_valeur, libelle, debit, credit, categorie
    columns=['date_operation', 'date_valeur', 'libelle', 'debit', 'credit', 'categorie']
    df = pd.DataFrame(transactionRows, columns=columns)
    # Set the debit and credit columns to float
    df['debit'] = df['debit'].apply(lambda x: -float(x) if x != '' else 0.0)
    df['credit'] = df['credit'].apply(lambda x: float(x) if x != '' else 0.0)
    # pd.set_option('display.max_rows', None)      # Show all rows
    # pd.set_option('display.max_columns', None)   # Show all columns
    # pd.set_option('display.width', 1000)         # Adjust width for readability
    # print(df)
    
    #Categorize transactions using rules defined in the database. The rules are stored in the categories table, with each row containing a category name and a comma-separated list of keywords. The categorize_from_rules method of the Classifier class will be used to categorize each transaction based on its libelle.
    categories = db.get_categories()
    for index, row in df.iterrows():
        category = cl.categorize_from_rules(row['libelle'], categories)
        df.at[index, 'categorie'] = category

    #Now categorize transaction with LLM recognition.
    targetCategories = [
        'Charge fixes (loyer, électricité, eau, internet, assurance)',
        'Telecommunications',
        'Alimentation + Restaurants',
        'Loisirs',
        'Revenus',
        'Epargne',
        'Autre'
    ]
    nonCategorized = df[df['categorie'].isnull()]
    categoryMatches = cl.categorize_with_llm(nonCategorized, targetCategories)
    if (categoryMatches != NULL):
        for category, keywords in categoryMatches:
            #Get first item that matches the category in the categories list. If it doesn't exist, add it to the database
            existingCat = None
            for cat in categories:
                if (cat[0] == category):
                    existingCat = cat
            if not existingCat:
                existingCat = (category, keywords)
            else:
                existingCat = (existingCat[0], existingCat[1] + ',' + keywords)
            db.upsert_category(existingCat[0], existingCat[1])

        for index, row in df.iterrows():
            category = cl.categorize_from_rules(row['libelle'], categories)
            df.at[index, 'categorie'] = category
    
    storeMonthlyBalanceInDatabase(rows)
    storeTransactionsInDatabase(df)

    
grouped = db.get_depense_grouped()

fig = px.pie(
    grouped,
    names="categorie",
    values="montant",
    title="Répartition des dépenses"
)

fig.show()


