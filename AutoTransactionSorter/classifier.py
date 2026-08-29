from asyncio.windows_events import NULL
import json

from openai import OpenAI

class Classifier:
    def __init__(self):
        self.OPENAI_API_KEY='<SECRET>'
        
        self.client = OpenAI(
            api_key=self.OPENAI_API_KEY
        )

    def categorize_from_rules(self, libelle, categories):
        libelle = libelle.upper()

        for category, keywords in categories:
            for keyword in keywords.split(','):
                if keyword.strip().upper() in libelle:
                    return category

        return None

    def categorize_with_llm(self, df, target_categories):
        # Use OpenAI API to categorize the transaction based on its libelle. The target categories are provided as a list of strings. The API will return the category that best matches the libelle.
        if df.empty:
            return NULL
        target_categories_str = ''
        for category in target_categories:
            target_categories_str += f"- {category}\n"
        transactions_str = ''
        for index, row in df.iterrows():
            transactions_str += f"- {row['libelle']}\n"
        prompt = f"Catégorise les transactions suivantes.\n\
\n\
Catégories autorisées : {target_categories_str}\n\
\n\
Retourne uniquement un tableau JSON d'objets avec une ligne par catégorie qui contient: 'category' le nom de la catégorie et 'keywords' des keywords séparés par des virgules pour catégoriser les transactions la prochaine fois.\n\
\n\
Transactions : {transactions_str}"
        print("Prompt for LLM categorization:", prompt)
        response = self.client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            n=1,
            stop=None,
            temperature=0.5,
        )
        
        # Parse the response to extract the category for each transaction. The response is expected to be a JSON array of objects with libelle and categorie fields.
        try:
            categorized_transactions = json.loads(response.choices[0].message.content)
            categoryMatches = []
            for transaction in categorized_transactions:
                category = transaction['category']
                keywords = transaction['keywords']
                categoryMatches.append((category, keywords))
            return categoryMatches
        except json.JSONDecodeError as e:
            return NULL




