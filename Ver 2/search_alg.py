import pandas as pd
import ast
from sentence_transformers import SentenceTransformer
from sentence_transformers import util
import torch
import pickle


# --- 1. Предобработка текста ---
def preprocess_recipe(row):
    name = row['name'] if isinstance(row['name'], str) else ''
    ingredients = ' '.join(ast.literal_eval(row['nor_ingridients'])) if isinstance(row['nor_ingridients'], str) else ''
    instructions = row['instructions'].lower() if isinstance(row['instructions'], str) else ''

    enhanced_text = (
        (name + ' ') * 2 +
        (ingredients + ' ') * 3 +
        (instructions + ' ') * 2
    ).strip().lower()

    return enhanced_text

# --- 2. Загрузка датасета ---
print("📁 Загрузка датасета...")
df = pd.read_csv("List_of_Recipes.csv")

# --- 3. Обработка текста ---
print("🧹 Обработка рецептов...")
df['clean_text'] = df.apply(preprocess_recipe, axis=1)

# --- 4. Загрузка модели ---
print("🧠 Загрузка модели...")
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

# # --- 5. Получение эмбеддингов ---
# print("🧬 Кодирование рецептов...")
# recipe_texts = df['clean_text'].tolist()
# recipe_embeddings = model.encode(recipe_texts, show_progress_bar=True)
# with open("recipe_embeddings.pkl", "wb") as f:
#     pickle.dump(recipe_embeddings, f)


# --- 5. Загрузка эмбеддингов ---
print("🧬 Загрузка эмбеддингов...")
with open("recipe_embeddings.pkl", "rb") as f:
    recipe_embeddings = pickle.load(f)


# --- 6. Функция поиска ---
def find_recipes(query, top_n=5):
    filtered_df = filter_by_keywords(df, query)
    filtered_indices = filtered_df.index.tolist()
    filtered_embeddings = recipe_embeddings[filtered_indices]
    
    query_embedding = model.encode([query.lower()])
    cos_scores = util.cos_sim(query_embedding, filtered_embeddings)[0]
    
    top_k = min(top_n * 3, len(filtered_indices))
    top_indices_in_subset = torch.topk(cos_scores, k=top_k).indices.tolist()
    result_indices = [filtered_indices[i] for i in top_indices_in_subset]

    results = []
    for idx in result_indices:
        results.append({
            'name': df.iloc[idx]['name'],
            'ingredients': df.iloc[idx]['pure_ingridients'],
            'instructions': df.iloc[idx]['instructions'],
            'score': cos_scores[result_indices.index(idx)].item()
        })
        if len(results) >= top_n:
            break

    return results

# --- 7. Функция предфильтрации ---
def filter_by_keywords(df, query, column='clean_text'):
    stopwords = {'в', 'на', 'с', 'по', 'для', 'из', 'от', 'до', 'и', 'или', 'не'}
    query_words = [word.strip() for word in query.lower().split(',') if word.strip() not in stopwords]

    filtered = df[df[column].apply(lambda x: all(word in x for word in query_words))]
    
    if filtered.empty:
        filtered = df[df[column].apply(lambda x: any(word in x for word in query_words))]

    return filtered if not filtered.empty else df

# --- 8. Основной блок ---
if __name__ == "__main__":
    user_query = input("Введите ваш запрос: ")

    print(f"\n🔍 Результаты по запросу: '{user_query}'")
    results = find_recipes(user_query, top_n=5)

    if not results:
        print("Ничего не найдено по вашему запросу.")
    else:
        for res in results:
            print("\n------------------------------")
            print(f"🍽️ {res['name']} | Score: {res['score']:.4f}")
            print(f"🧂 Ингредиенты: {res['ingredients']}")
            print(f"🧂 Как приготовить:\n {res['instructions']}")