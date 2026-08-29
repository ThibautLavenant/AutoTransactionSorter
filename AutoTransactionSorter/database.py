import sqlite3
import pandas as pd

class Database():
    def __init__(self, db_path="expenses.db"):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        # Create table transaction if it doesn't exist
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_operation TEXT,
            date_valeur TEXT,
            libelle TEXT,
            montant REAL,
            categorie TEXT
        )
        """)

        #Create table for categories if it doesn't exist
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            keywords TEXT
        )
        """)

        #Create table for monthly balance if it doesn't exist
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS monthly_balance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT,
            balance REAL
        )
        """)
        self.conn.commit()

    def upsert_monthly_balance(self, date, balance):
        # Save monthly balance in the database. Check if row with the same month already exists, if it does, update it, if not, insert it
        alreadyExistingRow = self.conn.execute("""
        SELECT id FROM monthly_balance WHERE month = ?
        """, (date,)).fetchone()
        if alreadyExistingRow:
            self.conn.execute("""
            UPDATE monthly_balance SET balance = ? WHERE id = ?
            """, (balance, alreadyExistingRow[0]))
        else:
            self.conn.execute("""
            INSERT INTO monthly_balance (month, balance) VALUES (?, ?)
            """, (date, balance))
        self.conn.commit()

    def upsert_transaction(self, df):
        #Save transactions in the database. Check if row with the same date_operation, date_valeur, libelle and montant already exists, if it does, update it, if not, insert it
        for index, row in df.iterrows():
            alreadyExistingRow = self.conn.execute("""
            SELECT id FROM transactions WHERE date_operation = ? AND date_valeur = ? AND libelle = ? AND montant = ?
            """, (row['date_operation'], row['date_valeur'], row['libelle'], row['debit'] + row['credit'])).fetchone()
            if alreadyExistingRow:
                self.conn.execute("""
                UPDATE transactions SET categorie = ? WHERE id = ?
                """, (row['categorie'], alreadyExistingRow[0]))
            else:
                self.conn.execute("""
                INSERT INTO transactions (date_operation, date_valeur, libelle, montant, categorie) VALUES (?, ?, ?, ?, ?)
                """, (row['date_operation'], row['date_valeur'], row['libelle'], row['debit'] + row['credit'], row['categorie']))
        self.conn.commit()

    def get_categories(self):
        #Get categories from the database. Return a list of tuples (category, keywords)
        categories = self.conn.execute("""
        SELECT name, keywords FROM categories
        """).fetchall()
        return categories

    def upsert_category(self, name, keywords):
        #Save category in the database. Check if row with the same name already exists, if it does, update it, if not, insert it
        alreadyExistingRow = self.conn.execute("""
        SELECT id, keywords FROM categories WHERE name = ?
        """, (name,)).fetchone()
        if alreadyExistingRow:
            self.conn.execute("""
            UPDATE categories SET keywords = ? WHERE id = ?
            """, (alreadyExistingRow[1] + ',' + keywords, alreadyExistingRow[0]))
        else:
            self.conn.execute("""
            INSERT INTO categories (name, keywords) VALUES (?, ?)
            """, (name, keywords))
        self.conn.commit()

    def get_depense_grouped(self):
        self.conn = sqlite3.connect("expenses.db")

        df = pd.read_sql_query("""
        SELECT categorie, montant
        FROM transactions
        WHERE montant < 0
        """, self.conn)
        df["montant"] = df["montant"].abs()
        #change all categories from Revenus to Alimentation + Restaurants
        df.loc[df["categorie"] == "Revenus", "categorie"] = "Alimentation + Restaurants"

        grouped = (
            df.groupby("categorie")["montant"]
              .sum()
              .reset_index()
        )
        return grouped